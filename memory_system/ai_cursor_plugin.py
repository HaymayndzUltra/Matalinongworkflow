"""
🤖 AI Cursor Plugin Interface
Direct integration for intelligent production deployment assistance
"""

import json
from pathlib import Path
from typing import Dict, Any
from memory_system.ai_cursor_intelligence import AIProductionIntelligence

class AICursorPlugin:
    """Plugin interface for AI Cursor to access production deployment intelligence"""
    
    def __init__(self):
        self.ai_intelligence = AIProductionIntelligence()
        self.memory_bank = Path("memory-bank")
        
    def query(self, user_input: str) -> Dict[str, Any]:
        """Main query interface for AI Cursor"""
        response = self.ai_intelligence.generate_intelligent_response(user_input)
        
        # Enhance response with direct file access
        response["file_contents"] = self._get_relevant_file_contents(response["relevant_documentation"])
        response["executable_commands"] = self._extract_executable_commands(response["immediate_actions"])
        
        return response
    
    def _get_relevant_file_contents(self, file_paths: list) -> Dict[str, str]:
        """Get actual file contents for immediate reference"""
        contents = {}
        for file_path in file_paths[:3]:  # Limit to first 3 files
            try:
                path = Path(file_path)
                if path.exists():
                    content = path.read_text(encoding='utf-8', errors='ignore')
                    # Truncate if too long
                    if len(content) > 2000:
                        content = content[:2000] + "\n... [truncated]"
                    contents[file_path] = content
            except Exception as e:
                contents[file_path] = f"Error reading file: {e}"
        return contents
    
    def _extract_executable_commands(self, actions: list) -> list:
        """Extract executable commands from action suggestions"""
        commands = []
        for action in actions:
            # Look for commands in backticks
            import re
            cmd_matches = re.findall(r'`([^`]+)`', action)
            commands.extend(cmd_matches)
        return commands
    
    def get_production_status(self) -> Dict[str, Any]:
        """Get current production deployment status"""
        return {
            "deployment_files_exist": self._check_deployment_files(),
            "git_branch_status": self._get_git_status(),
            "docker_status": self._get_docker_status(),
            "memory_bank_status": self._get_memory_bank_status()
        }
    
    def _check_deployment_files(self) -> Dict[str, bool]:
        """Check if key deployment files exist"""
        key_files = [
            "docs/AI_SYSTEM_PRODUCTION_DEPLOYMENT_SUMMARY.md",
            "docs/LOCAL_DEPLOYMENT_GUIDE.md",
            "scripts/security-hardening.sh",
            "scripts/setup-gpu-partitioning.sh",
            "main_pc_code/config/docker-compose.yml",
            "pc2_code/config/docker-compose.yml"
        ]
        
        return {file: Path(file).exists() for file in key_files}
    
    def _get_git_status(self) -> Dict[str, str]:
        """Get current git status"""
        try:
            import subprocess
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  capture_output=True, text=True)
            current_branch = result.stdout.strip()
            
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True)
            changes = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
            return {
                "current_branch": current_branch,
                "uncommitted_changes": changes,
                "target_branch": "cursor/reorganize-agent-groups-for-docker-production-deployment-8f25"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_docker_status(self) -> Dict[str, Any]:
        """Get Docker system status"""
        try:
            import subprocess
            # Check if Docker is running
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, text=True)
            docker_running = result.returncode == 0
            
            # Check running containers
            if docker_running:
                result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                                      capture_output=True, text=True)
                containers = result.stdout.strip()
            else:
                containers = "Docker not running"
            
            return {
                "docker_running": docker_running,
                "containers": containers
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_memory_bank_status(self) -> Dict[str, Any]:
        """Get memory bank status"""
        try:
            production_files = list(self.memory_bank.glob("production-*"))
            task_files = list((self.memory_bank / "queue-system").glob("*.json"))
            
            return {
                "production_docs_count": len(production_files),
                "task_files_exist": len(task_files) > 0,
                "memory_bank_size": sum(f.stat().st_size for f in self.memory_bank.rglob("*") if f.is_file())
            }
        except Exception as e:
            return {"error": str(e)}

# Global plugin instance for easy access
ai_cursor_plugin = AICursorPlugin()

def ai_cursor_query(user_input: str) -> str:
    """Simple function for AI Cursor to call directly"""
    response = ai_cursor_plugin.query(user_input)
    
    # Format response for AI Cursor
    formatted = f"""
🤖 AI PRODUCTION ASSISTANT RESPONSE

Query: {response['query']}
Confidence: {response['analysis']['confidence']}
Topic: {response['analysis']['topic']}

🎯 IMMEDIATE ACTIONS:
"""
    
    for i, action in enumerate(response['immediate_actions'][:5], 1):
        formatted += f"{i}. {action}\n"
    
    if response['executable_commands']:
        formatted += f"\n💻 EXECUTABLE COMMANDS:\n"
        for cmd in response['executable_commands'][:3]:
            formatted += f"• {cmd}\n"
    
    if response['potential_issues']:
        formatted += f"\n⚠️ POTENTIAL ISSUES:\n"
        for issue in response['potential_issues'][:3]:
            formatted += f"• {issue}\n"
    
    if response['relevant_documentation']:
        formatted += f"\n📚 RELEVANT FILES:\n"
        for file in response['relevant_documentation'][:3]:
            formatted += f"• {file}\n"
    
    formatted += f"\nGuidance: {response['guidance']}"
    
    return formatted

def ai_cursor_status() -> str:
    """Get production deployment status for AI Cursor"""
    status = ai_cursor_plugin.get_production_status()
    
    formatted = """
🚀 PRODUCTION DEPLOYMENT STATUS

📁 Deployment Files:
"""
    
    for file, exists in status['deployment_files_exist'].items():
        status_icon = "✅" if exists else "❌"
        formatted += f"{status_icon} {file}\n"
    
    formatted += f"""
🔧 Git Status:
• Current Branch: {status['git_branch_status'].get('current_branch', 'unknown')}
• Target Branch: {status['git_branch_status'].get('target_branch', 'unknown')}
• Uncommitted Changes: {status['git_branch_status'].get('uncommitted_changes', 0)}

🐳 Docker Status:
• Docker Running: {status['docker_status'].get('docker_running', False)}

🧠 Memory Bank:
• Production Docs: {status['memory_bank_status'].get('production_docs_count', 0)} files
• Memory Bank Size: {status['memory_bank_status'].get('memory_bank_size', 0)} bytes
"""
    
    return formatted

if __name__ == "__main__":
    # Test the plugin
    print("🔧 Testing AI Cursor Plugin...")
    
    test_queries = [
        "How do I deploy production?",
        "Docker containers failing",
        "Check system status"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(ai_cursor_query(query))
    
    print(f"\n{'='*50}")
    print("PRODUCTION STATUS:")
    print(ai_cursor_status())