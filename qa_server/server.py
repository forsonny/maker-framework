"""
MCP Server implementation for QA tools.

Implements the Model Context Protocol (MCP) using stdio transport
with JSON-RPC 2.0 message format. Provides tool registration and
dispatch for QA tools.
"""

import sys
import json
import logging
import signal
import inspect
import concurrent.futures
import threading
import time
import queue
from typing import Dict, Any, Callable, Optional, List

# Cross-platform non-blocking stdin handling
# On Windows, select exists but only works with sockets, not regular files like stdin
import platform

# Only use select on Unix-like systems where it works with stdin
HAS_SELECT = platform.system() != "Windows"
if HAS_SELECT:
    import select

# Configure module logger
logger = logging.getLogger(__name__)


class WindowsStdinReader:
    """Non-blocking stdin reader for Windows using a daemon thread.

    On Windows, sys.stdin.readline() blocks and cannot be interrupted,
    preventing graceful shutdown. This class uses a background daemon
    thread to read stdin and a queue for thread-safe communication,
    allowing readline with configurable timeout.
    """

    def __init__(self):
        """Initialize the reader with a queue and start the daemon thread."""
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        """Background loop that reads lines from stdin into the queue."""
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:  # EOF
                    self._queue.put(None)
                    break
                self._queue.put(line)
            except Exception:
                # Handle stdin errors gracefully
                self._queue.put(None)
                break

    def readline_with_timeout(self, timeout: float = 0.1) -> Optional[str]:
        """Read a line from stdin with timeout.

        Args:
            timeout: Maximum seconds to wait for input. Defaults to 0.1.

        Returns:
            The line read from stdin, or None on timeout or EOF.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        """Stop the reader thread."""
        self._running = False


# JSON-RPC 2.0 standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Maximum JSON-RPC message size (10 MB)
MAX_MESSAGE_SIZE = 10 * 1024 * 1024

# Import shared constants
from .constants import TOOL_TIMEOUT_SECONDS

# MCP Protocol version - update when implementing newer protocol features
# Format: YYYY-MM-DD per MCP specification
MCP_PROTOCOL_VERSION = "2024-11-05"

from dataclasses import dataclass, field


class CancellationToken:
    """Token for tracking and propagating cancellation requests.

    Used to signal cancellation to long-running tool operations.
    Thread-safe for use across the main server thread and executor threads.
    """

    def __init__(self, request_id: Any):
        """Initialize cancellation token.

        Args:
            request_id: The JSON-RPC request ID this token is associated with
        """
        self.request_id = request_id
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Signal cancellation. Thread-safe."""
        with self._lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested. Thread-safe."""
        with self._lock:
            return self._cancelled

    def __bool__(self) -> bool:
        """Allow using token in boolean context (True if NOT cancelled)."""
        return not self.is_cancelled()


class CancellationError(Exception):
    """Raised when an operation is cancelled via cancellation token.

    Tool handlers should raise this exception when they detect that their
    cancellation token has been cancelled, allowing for graceful cleanup
    and proper error reporting to the client.

    Example:
        def my_handler(arguments: Dict, cancellation_token: Optional[CancellationToken] = None):
            for item in long_list:
                if cancellation_token and cancellation_token.is_cancelled():
                    raise CancellationError("Operation was cancelled")
                process_item(item)
    """
    pass


def _validate_arguments(arguments: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    """Validate tool arguments against JSON schema.

    Returns error message if invalid, None if valid.
    Simple validation - checks required fields and basic types.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required fields
    for field in required:
        if field not in arguments:
            return f"Missing required field: {field}"

    # Check types for provided fields
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    for field, value in arguments.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type and expected_type in type_map:
                if not isinstance(value, type_map[expected_type]):
                    return f"Field '{field}' must be {expected_type}, got {type(value).__name__}"

    return None


def _detect_tool_error(result: Dict[str, Any]) -> bool:
    """Detect if a tool result contains validation or execution errors.
    
    Checks for common error indicators in tool results:
    - TestResult: failures with name containing 'error'
    - CoverageResult: uncovered_lines with file='error' or 'validation_error'
    - RegressionResult: regressions with name containing 'error'
    - generate_tests: error field present
    
    Args:
        result: Tool result dictionary
        
    Returns:
        True if result indicates an error condition
    """
    # Check for explicit error field (generate_tests)
    if result.get("error"):
        return True
    
    # Check failures list (TestResult)
    for failure in result.get("failures", []):
        name = failure.get("name", "")
        if "error" in name.lower():
            return True
    
    # Check uncovered_lines for errors (CoverageResult)
    for line in result.get("uncovered_lines", []):
        file_val = line.get("file", "")
        if file_val in ("error", "validation_error"):
            return True
    
    # Check regressions for errors (RegressionResult)
    for reg in result.get("regressions", []):
        name = reg.get("name", "")
        if "error" in name.lower():
            return True
    
    return False


@dataclass
class ToolSchema:
    """Schema definition for an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class RegisteredTool:
    """A registered tool with its handler and schema.

    The handler can optionally accept a second parameter for cancellation_token:
    - handler(arguments: Dict[str, Any]) -> Any
    - handler(arguments: Dict[str, Any], cancellation_token: Optional[CancellationToken]) -> Any
    
    IMPORTANT: Tool handlers SHOULD check the cancellation token periodically during 
    long-running operations to enable graceful cancellation:
    
    def my_handler(arguments: Dict, cancellation_token: Optional[CancellationToken] = None):
        for item in long_list:
            # Check for cancellation before expensive operations
            if cancellation_token and cancellation_token.is_cancelled():
                raise CancellationError("Operation was cancelled")
            
            # Perform work...
            process_item(item)
        
        return result
    
    Tools that ignore cancellation tokens may continue running indefinitely even
    after the client has cancelled the request, wasting resources and delaying
    other operations.
    """
    schema: ToolSchema
    handler: Callable[[Dict[str, Any]], Any]


class MCPServer:
    """MCP Server using stdio transport and JSON-RPC 2.0.

    This server implements the MCP protocol for exposing QA tools
    to Claude Code and maker-reviewer.

    Usage:
        server = MCPServer()
        server.register_tool("run_tests", run_tests_handler, schema)
        server.run()
    """

    def __init__(self, name: str = "claude-qa", version: str = "1.0.0"):
        """Initialize MCP server.

        Args:
            name: Server name for identification
            version: Server version string
        """
        self.name = name
        self.version = version
        self.tool_registry: Dict[str, RegisteredTool] = {}
        self._running_event = threading.Event()
        self._running_event.set()  # Start as "running"
        self._initialized = False
        self._active_cancellation_tokens: Dict[Any, CancellationToken] = {}
        self._tokens_lock = threading.Lock()
        self._current_request_id: Optional[Any] = None  # Set during request handling
        self._stdin_reader: Optional[WindowsStdinReader] = None  # Created lazily in run() on Windows

    def register_tool(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Any],
        description: str,
        input_schema: Dict[str, Any],
    ) -> None:
        """Register a tool with the server.

        Args:
            name: Tool name (will be available as mcp__claude-qa__{name})
            handler: Function to call when tool is invoked
            description: Human-readable description of the tool
            input_schema: JSON Schema for tool input parameters
        """
        schema = ToolSchema(
            name=name,
            description=description,
            input_schema=input_schema,
        )
        self.tool_registry[name] = RegisteredTool(schema=schema, handler=handler)

    def parse_message(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON-RPC 2.0 message from input.

        Args:
            line: Raw input line

        Returns:
            Parsed message dict or None if structure invalid

        Raises:
            json.JSONDecodeError: If JSON parsing fails (for PARSE_ERROR response)
        """
        # Let JSON decode errors propagate to caller for proper PARSE_ERROR handling
        parsed = json.loads(line.strip())
        
        # Check for batch requests (JSON arrays) - not currently supported
        if isinstance(parsed, list):
            # Batch requests are valid JSON-RPC 2.0 but not implemented
            raise NotImplementedError("Batch requests are not supported")
        
        # Validate JSON-RPC 2.0 structure (returns None for INVALID_REQUEST)
        if not isinstance(parsed, dict):
            return None
        if parsed.get("jsonrpc") != "2.0":
            return None
        return parsed

    def format_response(
        self,
        request_id: Any,
        result: Any = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a JSON-RPC 2.0 response.

        Args:
            request_id: ID from the request
            result: Success result (mutually exclusive with error)
            error: Error object with code and message

        Returns:
            JSON string of the response
        """
        response: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
        }
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
        return json.dumps(response)

    def format_error(
        self,
        code: int,
        message: str,
        data: Any = None,
    ) -> Dict[str, Any]:
        """Format a JSON-RPC 2.0 error object.

        Args:
            code: Error code (negative for standard errors)
            message: Human-readable error message
            data: Additional error data

        Returns:
            Error dict for use in format_response
        """
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return error

    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request.

        Returns server capabilities and info.
        Validates client protocol version for compatibility.

        Raises:
            ValueError: If client protocol version is incompatible (more than 1 year old)
        """
        # Check client protocol version if provided
        client_version = params.get("protocolVersion")
        if client_version:
            # Extract major version (year) for compatibility check
            try:
                server_year = int(MCP_PROTOCOL_VERSION.split("-")[0])
                client_year = int(client_version.split("-")[0])
            except (ValueError, TypeError, IndexError):
                logger.debug(f"Could not parse protocol version: {client_version}")
            else:
                if client_year < server_year - 1:  # Allow 1 year back for compatibility
                    raise ValueError(
                        f"Client protocol version {client_version} is incompatible "
                        f"with server version {MCP_PROTOCOL_VERSION}. "
                        f"Please upgrade your client."
                    )

        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,  # Server tools are static
                },
                "resources": {},
                "prompts": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request.

        Returns list of all registered tools with their schemas.
        """
        tools = []
        for name, tool in self.tool_registry.items():
            tools.append({
                "name": name,
                "description": tool.schema.description,
                "inputSchema": tool.schema.input_schema,
            })
        return {"tools": tools}

    def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request.

        Returns empty list as this server does not provide resources.
        """
        return {"resources": []}

    def handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request.

        Returns empty list as this server does not provide prompts.
        """
        return {"prompts": []}

    def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request.

        Dispatches to the appropriate tool handler.

        Args:
            params: Request params containing name and arguments

        Returns:
            Tool result wrapped in content array

        Raises:
            ValueError: If tool not found, server not initialized, or execution fails
        """
        if not self._initialized:
            raise ValueError(
                "Server not initialized. The client must send an 'initialize' request "
                "followed by a 'notifications/initialized' notification before calling tools."
            )

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tool_registry:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tool_registry[tool_name]

        # Validate arguments against schema
        validation_error = _validate_arguments(arguments, tool.schema.input_schema)
        if validation_error:
            raise ValueError(validation_error)

        # Create cancellation token for this request
        request_id = self._current_request_id
        cancellation_token = CancellationToken(request_id) if request_id else None

        # Register token for potential cancellation
        if cancellation_token and request_id is not None:
            with self._tokens_lock:
                self._active_cancellation_tokens[request_id] = cancellation_token

        try:
            # Create wrapper for backward-compatible cancellation token passing
            def handler_wrapper():
                """Invoke handler with optional cancellation_token parameter."""
                try:
                    sig = inspect.signature(tool.handler)
                    if len(sig.parameters) >= 2:
                        return tool.handler(arguments, cancellation_token)
                    else:
                        return tool.handler(arguments)
                except (ValueError, TypeError):
                    # If signature inspection fails, call without token
                    return tool.handler(arguments)

            # Execute with timeout using daemon thread to prevent zombie processes
            result_container = {'result': None, 'exception': None}
            
            def run_in_daemon_thread():
                """Run handler in daemon thread to prevent hanging on process exit."""
                try:
                    result_container['result'] = handler_wrapper()
                except Exception as e:
                    result_container['exception'] = e
                    
            thread = threading.Thread(target=run_in_daemon_thread, daemon=True)
            thread.start()
            thread.join(timeout=TOOL_TIMEOUT_SECONDS)
            
            if thread.is_alive():
                # Thread is still running after timeout
                logger.warning(
                    f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT_SECONDS}s; "
                    f"daemon thread may still be running and consuming resources"
                )
                if cancellation_token:
                    cancellation_token.cancel()
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "error": f"Tool execution timed out after {TOOL_TIMEOUT_SECONDS} seconds",
                                "code": "TIMEOUT_ERROR",
                            }),
                        }
                    ],
                    "isError": True,
                }
                
            if result_container['exception']:
                raise result_container['exception']
                
            result = result_container['result']
            if result is None and result_container['exception'] is None:
                # Thread finished but no result - this shouldn't happen
                raise RuntimeError("Tool execution completed but returned no result")

            # Check if cancelled during execution
            if cancellation_token and cancellation_token.is_cancelled():
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "error": "Tool execution was cancelled",
                                "code": "CANCELLED",
                            }),
                        }
                    ],
                    "isError": True,
                }

            # Detect if result contains validation/execution errors
            is_error = _detect_tool_error(result)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2),
                    }
                ],
                "isError": is_error,
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "error": str(e),
                            "code": "TOOL_ERROR",
                        }),
                    }
                ],
                "isError": True,
            }
        finally:
            # Clean up cancellation token
            if request_id is not None:
                with self._tokens_lock:
                    self._active_cancellation_tokens.pop(request_id, None)

    def handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request for health checks.

        Returns a simple response to verify server is alive.
        """
        return {"status": "ok", "server": self.name, "version": self.version}

    def handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown request.

        Signals the server to stop after sending response.
        MCP protocol shutdown method.
        """
        self._running_event.clear()
        return {}

    def handle_request(self, message: Dict[str, Any]) -> Optional[str]:
        """Handle an incoming JSON-RPC request.

        Args:
            message: Parsed JSON-RPC message

        Returns:
            Response string or None for notifications
        """
        request_id = message.get("id")
        
        # Validate method field is present per JSON-RPC 2.0 spec
        if "method" not in message:
            if request_id is not None:  # Only respond to requests, not notifications
                return self.format_response(
                    request_id,
                    error=self.format_error(INVALID_REQUEST, "Missing required 'method' field"),
                )
            return None
            
        method = message.get("method", "")
        params = message.get("params", {})

        # Map methods to handlers
        handlers: Dict[str, Callable] = {
            "initialize": self.handle_initialize,
            "shutdown": self.handle_shutdown,
            "ping": self.handle_ping,
            "tools/list": self.handle_tools_list,
            "tools/call": self.handle_tools_call,
            "resources/list": self.handle_resources_list,
            "prompts/list": self.handle_prompts_list,
        }

        # Handle notifications (no response needed)
        if request_id is None:
            if method == "notifications/initialized":
                self._initialized = True
                return None
            if method == "notifications/cancelled":
                # Propagate cancellation to active tool execution
                cancelled_request_id = params.get("requestId")
                if cancelled_request_id is not None:
                    with self._tokens_lock:
                        token = self._active_cancellation_tokens.get(cancelled_request_id)
                        if token:
                            token.cancel()
                            logger.info(f"Cancelled request {cancelled_request_id}")
                return None
            if method == "notifications/progress":
                # Log progress notifications for debugging
                progress_token = params.get("progressToken")
                progress = params.get("progress")
                total = params.get("total")
                logger.debug(f"Progress notification: token={progress_token}, progress={progress}/{total}")
                return None
            if method == "notifications/resources/list_changed":
                # Resource list changed - no action needed for QA server
                logger.debug("Resources list changed notification received")
                return None
            if method == "notifications/tools/list_changed":
                # Tool list changed - no action needed for QA server  
                logger.debug("Tools list changed notification received")
                return None
            if method == "notifications/prompts/list_changed":
                # Prompts list changed - no action needed for QA server
                logger.debug("Prompts list changed notification received")
                return None
            if method == "notifications/message":
                # General message notification
                role = params.get("role", "assistant")
                content = params.get("content", {})
                logger.debug(f"Message notification: role={role}, content={content}")
                return None
            if method == "$/cancelRequest":
                # Alternative cancel format - handle same as notifications/cancelled
                cancelled_request_id = params.get("id")
                if cancelled_request_id is not None:
                    with self._tokens_lock:
                        token = self._active_cancellation_tokens.get(cancelled_request_id)
                        if token:
                            token.cancel()
                            logger.info(f"Cancelled request {cancelled_request_id} ($/cancelRequest)")
                return None
            # Log unknown notifications for debugging
            logger.warning(f"Received unknown notification: {method}")
            return None

        # Handle requests
        if method in handlers:
            try:
                # Store current request_id for cancellation token creation
                self._current_request_id = request_id
                result = handlers[method](params)
                return self.format_response(request_id, result=result)
            except ValueError as e:
                # ValueError from tools/call indicates invalid params (unknown tool)
                error = self.format_error(INVALID_PARAMS, str(e))
                return self.format_response(request_id, error=error)
            except Exception as e:
                error = self.format_error(INTERNAL_ERROR, f"Internal error: {e}")
                return self.format_response(request_id, error=error)
        else:
            error = self.format_error(METHOD_NOT_FOUND, f"Method not found: {method}")
            return self.format_response(request_id, error=error)

    def run(self) -> None:
        """Run the MCP server, reading from stdin and writing to stdout.

        This is a blocking call that runs until EOF on stdin or shutdown is called.
        """
        self._running_event.set()

        # Register signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._running_event.clear()

        # SIGHUP handler for config reload
        def sighup_handler(signum, frame):
            logger.info("Received SIGHUP, reloading configuration...")
            # Clear config cache to force reload on next access
            from .config import clear_config_cache
            clear_config_cache()
            logger.info("Configuration cache cleared, will reload on next use")
        
        # Register handlers - SIGTERM/SIGHUP may not exist on all platforms
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, sighup_handler)

        logger.info("Server starting...")
        print(f"[QA MCP] Server starting...", file=sys.stderr)

        # Simple rate limiting - track messages per second
        message_times = []
        MAX_MESSAGES_PER_SECOND = 100
        
        try:
            # Use non-blocking stdin read with timeout for graceful shutdown
            while self._running_event.is_set():
                try:
                    # Check for available input with timeout
                    if HAS_SELECT:
                        # Unix/Linux: use select with timeout
                        ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if not ready:
                            continue
                        line = sys.stdin.readline()
                        if not line:  # EOF
                            break
                    else:
                        # Windows: use WindowsStdinReader for non-blocking reads
                        # This allows checking _running_event between timeout intervals
                        if self._stdin_reader is None:
                            self._stdin_reader = WindowsStdinReader()
                        line = self._stdin_reader.readline_with_timeout(timeout=0.1)
                        if line is None:
                            # Timeout - check _running_event and continue loop
                            continue
                        if line == "":  # EOF (empty string, not None)
                            break
                    
                    if not self._running_event.is_set():
                        break

                    # Check message size limit
                    if len(line) > MAX_MESSAGE_SIZE:
                        logger.warning(f"Message exceeds size limit: {len(line)} bytes")
                        error_response = self.format_response(
                            None,
                            error=self.format_error(PARSE_ERROR, f"Message too large (max {MAX_MESSAGE_SIZE} bytes)"),
                        )
                        print(error_response, flush=True)
                        continue

                    if not line.strip():
                        continue
                    
                    # Rate limiting check
                    current_time = time.time()
                    # Remove messages older than 1 second
                    message_times = [t for t in message_times if current_time - t < 1.0]
                    
                    if len(message_times) >= MAX_MESSAGES_PER_SECOND:
                        logger.warning("Rate limit exceeded, dropping message")
                        error_response = self.format_response(
                            None,
                            error=self.format_error(INTERNAL_ERROR, "Rate limit exceeded"),
                        )
                        print(error_response, flush=True)
                        continue
                    
                    message_times.append(current_time)
                except (EOFError, KeyboardInterrupt):
                    # Graceful shutdown on EOF or Ctrl+C
                    break
                except UnicodeDecodeError as e:
                    # Handle encoding errors gracefully
                    logger.error(f"Unicode decode error on stdin: {e}")
                    # Try to send error response
                    error_response = self.format_response(
                        None,
                        error=self.format_error(PARSE_ERROR, "Invalid UTF-8 encoding"),
                    )
                    try:
                        print(error_response, flush=True)
                    except Exception:
                        pass  # If we can't even write, just continue
                    continue
                except OSError as e:
                    # Handle stdin errors
                    logger.error(f"Stdin error: {e}")
                    break

                try:
                    message = self.parse_message(line)
                except json.JSONDecodeError:
                    # JSON parsing failed, send PARSE_ERROR
                    logger.warning("Received malformed JSON")
                    error_response = self.format_response(
                        None,
                        error=self.format_error(PARSE_ERROR, "Parse error"),
                    )
                    print(error_response, flush=True)
                    continue
                except NotImplementedError as e:
                    # Batch requests are not supported - return METHOD_NOT_FOUND
                    logger.warning("Received batch request (not supported)")
                    error_response = self.format_response(
                        None,
                        error=self.format_error(METHOD_NOT_FOUND, str(e)),
                    )
                    print(error_response, flush=True)
                    continue
                
                if message is None:
                    # Valid JSON but invalid JSON-RPC structure, send INVALID_REQUEST
                    logger.warning("Received invalid JSON-RPC message structure")
                    error_response = self.format_response(
                        None,
                        error=self.format_error(INVALID_REQUEST, "Invalid Request"),
                    )
                    print(error_response, flush=True)
                    continue

                response = self.handle_request(message)
                if response is not None:
                    print(response, flush=True)

                # Check if shutdown was called
                if not self._running_event.is_set():
                    break

        except KeyboardInterrupt:
            logger.info("Server interrupted by keyboard")
            print(f"[QA MCP] Server interrupted", file=sys.stderr)
        finally:
            # Clean up Windows stdin reader thread if it exists
            if self._stdin_reader is not None:
                try:
                    self._stdin_reader.stop()
                except Exception as e:
                    logger.debug(f"Error stopping stdin reader: {e}")
            self._running_event.clear()
            logger.info("Server stopped")
            print(f"[QA MCP] Server stopped", file=sys.stderr)

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running_event.clear()
