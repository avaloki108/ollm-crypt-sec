#!/usr/bin/env python3
"""
MCP Bash Server - Execute shell commands safely
Includes web3se-lab integration for advanced Web3 scanning
"""
import asyncio
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize the server
server = Server("bash-server")

# Add ~/tools to PATH for tool execution
TOOLS_DIR = Path.home() / "tools"
WEB3SE_LAB_DIR = TOOLS_DIR / "web3se-lab"
DEFAULT_ENV = dict(os.environ)
DEFAULT_ENV["PATH"] = f"{TOOLS_DIR}:{str(WEB3SE_LAB_DIR)}:{DEFAULT_ENV.get('PATH', '')}"
# Set web3se-lab API endpoints
DEFAULT_ENV["SMARTBERT_API"] = os.environ.get("SMARTBERT_API", "http://localhost:9900")
DEFAULT_ENV["WEB3_SEKIT_API"] = os.environ.get("WEB3_SEKIT_API", "http://localhost:8081")


def find_tool_executable(tool_name: str) -> Optional[Dict[str, str]]:
    """Find how to execute a security tool from ~/tools.
    
    Returns a dict with 'command', 'cwd', and 'description' if found, None otherwise.
    """
    tool_name_lower = tool_name.lower()
    
    # Tool definitions with their execution methods
    tool_configs = {
        "slither": {
            "dir": TOOLS_DIR / "slither",
            "command": "python3 slither/slither.py",
            "description": "Slither static analyzer"
        },
        "mythril": {
            "dir": TOOLS_DIR / "mythril2.0",
            "command": "python3 mythril/mythril",
            "description": "Mythril security analyzer"
        },
        "echidna": {
            "dir": TOOLS_DIR / "echidna",
            "command": "echidna-test",  # May need to be built first
            "description": "Echidna fuzzing tool"
        },
        "securify2": {
            "dir": TOOLS_DIR / "securify2",
            "command": "python3 -m securify",
            "description": "Securify2 static analyzer"
        },
        "securify": {
            "dir": TOOLS_DIR / "securify2",
            "command": "python3 -m securify",
            "description": "Securify2 static analyzer"
        },
        "medusa": {
            "dir": TOOLS_DIR / "medusa",
            "command": "python3 -m medusa",
            "description": "Medusa fuzzing tool"
        },
        "fuzz-utils": {
            "dir": TOOLS_DIR / "fuzz-utils",
            "command": "python3 -m fuzz_utils",
            "description": "Fuzz utilities"
        },
        "solc-select": {
            "dir": TOOLS_DIR / "solc-select",
            "command": "solc-select",  # Usually installed globally
            "description": "Solidity compiler version selector"
        }
    }
    
    # Check if tool is defined
    if tool_name_lower not in tool_configs:
        return None
    
    config = tool_configs[tool_name_lower]
    tool_dir = config["dir"]
    
    # Check if directory exists
    if not tool_dir.exists():
        return None
    
    # Try to find actual executable
    # Check for common executable locations
    possible_paths = [
        tool_dir / tool_name,
        tool_dir / tool_name_lower,
        tool_dir / "bin" / tool_name,
        tool_dir / "bin" / tool_name_lower,
    ]
    
    # For Python tools, check if the module path exists
    if "python3" in config["command"]:
        # Verify the Python file/module exists
        parts = config["command"].split()[1:]  # Remove 'python3'
        if parts:
            module_path = tool_dir / parts[0].replace(".", "/")
            if module_path.exists() or (module_path / "__init__.py").exists():
                return {
                    "command": config["command"],
                    "cwd": str(tool_dir),
                    "description": config["description"]
                }
    
    # For direct executables (like solc-select)
    for path in possible_paths:
        if path.exists() and os.access(path, os.X_OK):
            return {
                "command": str(path),
                "cwd": str(tool_dir),
                "description": config["description"]
            }
    
    # Even if executable not found, return config if directory exists
    # (tool might need to be run differently)
    return {
        "command": config["command"],
        "cwd": str(tool_dir),
        "description": config["description"]
    }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="execute_command",
            description="Execute a shell command and return the output. Use this to run tools like slither, mythril, echidna, securify2, medusa, fuzz-utils, solc-select, foundry, etc. from ~/tools. The server automatically finds tools in ~/tools subdirectories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute. Examples:\n- 'slither .' or 'cd ~/tools/slither && python3 slither/slither.py .'\n- 'mythril analyze Contract.sol' or 'cd ~/tools/mythril2.0 && python3 mythril/mythril analyze Contract.sol'\n- 'echidna-test Contract.sol'\n- 'securify2 Contract.sol'\n- 'solc-select install 0.8.20'\n- 'forge test -vvv'"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the command (default: current directory)",
                        "default": "."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 300)",
                        "default": 300
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="run_security_tool",
            description="Run a security tool from ~/tools with automatic discovery. Supports: slither, mythril, echidna, securify2, medusa, fuzz-utils, solc-select. Automatically finds the correct execution method.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool: slither, mythril, echidna, securify2, medusa, fuzz-utils, or solc-select"
                    },
                    "arguments": {
                        "type": "string",
                        "description": "Arguments to pass to the tool (e.g., '.', 'analyze Contract.sol', 'test Contract.sol')"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the command (default: current directory)",
                        "default": "."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 300)",
                        "default": 300
                    }
                },
                "required": ["tool_name", "arguments"]
            }
        ),
        Tool(
            name="check_tool_available",
            description="Check if a tool is available in PATH or ~/tools",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to check (e.g., 'slither', 'forge', 'mythril')"
                    }
                },
                "required": ["tool_name"]
            }
        ),
        Tool(
            name="web3_scanner_scan",
            description="Scan a Web3 repository using web3se-lab scanner. Generates embeddings and detects malicious intents. Requires web3se-lab services to be running.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_path": {
                        "type": "string",
                        "description": "Path to repository or GitHub URL (e.g., './my-contracts' or 'https://github.com/user/repo')"
                    },
                    "with_intent": {
                        "type": "boolean",
                        "description": "Detect malicious intents (default: true)",
                        "default": True
                    },
                    "with_embed": {
                        "type": "boolean",
                        "description": "Generate embeddings (default: true)",
                        "default": True
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Output JSON file path (optional)"
                    }
                },
                "required": ["repository_path"]
            }
        ),
        Tool(
            name="start_web3se_services",
            description="Start web3se-lab services (SmartBERT API on port 9900 and web3-sekit API on port 8081). Returns status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "background": {
                        "type": "boolean",
                        "description": "Run in background (default: false)",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="check_web3se_status",
            description="Check if web3se-lab services (SmartBERT and web3-sekit) are running",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "execute_command":
        command = arguments.get("command", "")
        working_dir = arguments.get("working_directory", ".")
        timeout = arguments.get("timeout", 300)
        
        if not command:
            return [TextContent(
                type="text",
                text="Error: No command provided"
            )]
        
        try:
            # Resolve working directory
            work_dir = Path(working_dir).expanduser().resolve()
            if not work_dir.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: Working directory does not exist: {work_dir}"
                )]
            
            # Prepare environment with ~/tools in PATH
            env = dict(DEFAULT_ENV)
            tools_path = str(TOOLS_DIR)
            current_path = env.get("PATH", "")
            if tools_path not in current_path:
                env["PATH"] = f"{tools_path}:{current_path}"
            
            # Execute command using shell to handle complex commands
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
                env=env,
                shell=True
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return [TextContent(
                    type="text",
                    text=f"Error: Command timed out after {timeout} seconds\nCommand: {command}"
                )]
            
            # Format output
            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")
            
            result = f"Command: {command}\n"
            result += f"Working Directory: {work_dir}\n"
            result += f"Exit Code: {process.returncode}\n"
            result += "=" * 50 + "\n"
            
            if output:
                result += "STDOUT:\n" + output + "\n"
            
            if error_output:
                result += "STDERR:\n" + error_output + "\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error executing command: {str(e)}\nCommand: {command}"
            )]
    
    elif name == "check_tool_available":
        tool_name = arguments.get("tool_name", "")
        
        if not tool_name:
            return [TextContent(
                type="text",
                text="Error: No tool name provided"
            )]
        
        try:
            # Check in PATH
            result = subprocess.run(
                ["which", tool_name],
                capture_output=True,
                text=True,
                env=DEFAULT_ENV,
                timeout=5
            )
            
            if result.returncode == 0:
                tool_path = result.stdout.strip()
                return [TextContent(
                    type="text",
                    text=f"Tool '{tool_name}' is available at: {tool_path}"
                )]
            else:
                # Try to find tool using our discovery function
                tool_info = find_tool_executable(tool_name)
                if tool_info:
                    return [TextContent(
                        type="text",
                        text=f"Tool '{tool_name}' found:\n"
                             f"  {tool_info['description']}\n"
                             f"  Command: {tool_info['command']}\n"
                             f"  Directory: {tool_info['cwd']}\n"
                             f"\nUsage example:\n"
                             f"  cd {tool_info['cwd']} && {tool_info['command']} <args>"
                    )]
                
                # Check common tool directories
                tool_dirs = [
                    TOOLS_DIR / tool_name,
                    TOOLS_DIR / tool_name / tool_name,
                    TOOLS_DIR / f"{tool_name}2.0" / tool_name,
                    WEB3SE_LAB_DIR / tool_name,
                ]
                
                for tool_dir in tool_dirs:
                    if tool_dir.exists() and tool_dir.is_dir():
                        # Check for executable inside
                        for possible_exec in [tool_dir / tool_name, tool_dir / "bin" / tool_name]:
                            if possible_exec.exists() and os.access(possible_exec, os.X_OK):
                                return [TextContent(
                                    type="text",
                                    text=f"Tool '{tool_name}' found in ~/tools at: {possible_exec}"
                                )]
                
                return [TextContent(
                    type="text",
                    text=f"Tool '{tool_name}' not found in PATH or ~/tools.\n"
                         f"Available tools in ~/tools: echidna, fuzz-utils, medusa, mythril2.0, securify2, slither, solc-select"
                )]
                
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking tool: {str(e)}"
            )]
    
    elif name == "run_security_tool":
        tool_name = arguments.get("tool_name", "").lower()
        tool_args = arguments.get("arguments", "")
        working_dir = arguments.get("working_directory", ".")
        timeout = arguments.get("timeout", 300)
        
        if not tool_name:
            return [TextContent(
                type="text",
                text="Error: No tool name provided. Supported tools: slither, mythril, echidna, securify2, medusa, fuzz-utils, solc-select"
            )]
        
        # Find the tool
        tool_info = find_tool_executable(tool_name)
        if not tool_info:
            # Try common variations
            if tool_name == "securify":
                tool_info = find_tool_executable("securify2")
            
            if not tool_info:
                return [TextContent(
                    type="text",
                    text=f"Error: Tool '{tool_name}' not found.\n"
                         f"Supported tools: slither, mythril, echidna, securify2, medusa, fuzz-utils, solc-select\n"
                         f"Use 'check_tool_available' to find how to run a specific tool."
                )]
        
        try:
            # Build command
            full_command = f"{tool_info['command']} {tool_args}".strip()
            work_dir = Path(working_dir).expanduser().resolve()
            tool_cwd = Path(tool_info['cwd']).expanduser().resolve()
            
            # Use tool's directory or specified working directory
            exec_cwd = str(tool_cwd) if tool_cwd.exists() else str(work_dir)
            
            # Prepare environment
            env = dict(DEFAULT_ENV)
            tools_path = str(TOOLS_DIR)
            current_path = env.get("PATH", "")
            if tools_path not in current_path:
                env["PATH"] = f"{tools_path}:{current_path}"
            
            # Execute
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_cwd,
                env=env,
                shell=True
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return [TextContent(
                    type="text",
                    text=f"Error: Tool execution timed out after {timeout} seconds\n"
                         f"Tool: {tool_name}\n"
                         f"Command: {full_command}"
                )]
            
            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")
            
            result = f"Security Tool Execution: {tool_name}\n"
            result += f"Command: {full_command}\n"
            result += f"Working Directory: {exec_cwd}\n"
            result += f"Exit Code: {process.returncode}\n"
            result += "=" * 50 + "\n"
            
            if output:
                result += "STDOUT:\n" + output + "\n"
            
            if error_output:
                result += "STDERR:\n" + error_output + "\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error running security tool: {str(e)}\n"
                     f"Tool: {tool_name}\n"
                     f"Arguments: {tool_args}"
            )]
    
    elif name == "web3_scanner_scan":
        repo_path = arguments.get("repository_path", "")
        with_intent = arguments.get("with_intent", True)
        with_embed = arguments.get("with_embed", True)
        output_file = arguments.get("output_file", "")
        
        if not repo_path:
            return [TextContent(
                type="text",
                text="Error: No repository path provided"
            )]
        
        try:
            # Build web3-scanner command
            web3_scanner = WEB3SE_LAB_DIR / "web3-scanner"
            if not web3_scanner.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: web3-scanner not found at {web3_scanner}"
                )]
            
            cmd_parts = [str(web3_scanner), "scan", repo_path]
            if with_intent:
                cmd_parts.append("--intent")
            if with_embed:
                cmd_parts.append("--embed")
            if output_file:
                cmd_parts.extend(["--output", output_file])
            
            command = " ".join(cmd_parts)
            
            # Execute
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WEB3SE_LAB_DIR),
                env=DEFAULT_ENV,
                shell=True
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=600  # 10 minutes for scanning
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return [TextContent(
                    type="text",
                    text=f"Error: Scan timed out after 10 minutes\nCommand: {command}"
                )]
            
            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")
            
            result = f"Web3 Scanner Results:\n"
            result += f"Repository: {repo_path}\n"
            result += f"Exit Code: {process.returncode}\n"
            result += "=" * 50 + "\n"
            
            if output:
                result += "STDOUT:\n" + output + "\n"
            
            if error_output:
                result += "STDERR:\n" + error_output + "\n"
            
            if output_file and Path(output_file).exists():
                result += f"\n✅ Results saved to: {output_file}\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error running web3-scanner: {str(e)}\nRepository: {repo_path}"
            )]
    
    elif name == "start_web3se_services":
        background = arguments.get("background", False)
        
        try:
            web3_scanner = WEB3SE_LAB_DIR / "web3-scanner"
            if not web3_scanner.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: web3-scanner not found at {web3_scanner}"
                )]
            
            # Start services
            if background:
                # Run in background
                process = await asyncio.create_subprocess_shell(
                    f"cd {WEB3SE_LAB_DIR} && nohup {web3_scanner} start > /dev/null 2>&1 &",
                    shell=True,
                    env=DEFAULT_ENV
                )
                await process.wait()
                
                # Wait a bit and check status
                await asyncio.sleep(5)
                status_result = await call_tool("check_web3se_status", {})
                return status_result
            else:
                # Note: This will block, so we'll just start it and return immediately
                # In practice, services should be started manually before scanning
                return [TextContent(
                    type="text",
                    text="To start web3se-lab services, run:\n"
                         f"cd {WEB3SE_LAB_DIR} && ./web3-scanner start\n\n"
                         "Or use: bash-server.execute_command with command: "
                         f"'cd {WEB3SE_LAB_DIR} && ./web3-scanner start'\n\n"
                         "Services will run on:\n"
                         "- SmartBERT API: http://localhost:9900\n"
                         "- web3-sekit API: http://localhost:8081"
                )]
                
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error starting services: {str(e)}"
            )]
    
    elif name == "check_web3se_status":
        try:
            status_results = []
            
            # Check SmartBERT API
            smartbert_url = DEFAULT_ENV.get("SMARTBERT_API", "http://localhost:9900")
            try:
                with urllib.request.urlopen(smartbert_url, timeout=2) as response:
                    data = json.loads(response.read().decode())
                    status_results.append(f"✅ SmartBERT API: Running at {smartbert_url}")
                    if isinstance(data, dict):
                        status_results.append(f"   Model: {data.get('model', 'unknown')}")
            except Exception as e:
                status_results.append(f"❌ SmartBERT API: Not running at {smartbert_url}")
                status_results.append(f"   Error: {str(e)}")
            
            # Check web3-sekit API
            web3sekit_url = DEFAULT_ENV.get("WEB3_SEKIT_API", "http://localhost:8081")
            try:
                with urllib.request.urlopen(web3sekit_url, timeout=2) as response:
                    status_results.append(f"✅ web3-sekit API: Running at {web3sekit_url}")
            except Exception:
                status_results.append(f"❌ web3-sekit API: Not running at {web3sekit_url}")
            
            # Check web3-scanner CLI
            web3_scanner = WEB3SE_LAB_DIR / "web3-scanner"
            if web3_scanner.exists():
                status_results.append(f"✅ web3-scanner CLI: Available at {web3_scanner}")
            else:
                status_results.append(f"❌ web3-scanner CLI: Not found at {web3_scanner}")
            
            return [TextContent(
                type="text",
                text="web3se-lab Service Status:\n" + "\n".join(status_results)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error checking web3se-lab status: {str(e)}"
            )]
    
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
