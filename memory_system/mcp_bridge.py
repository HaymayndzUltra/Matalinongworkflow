#!/usr/bin/env python3
"""
MCP Memory Bridge
Provides MCP-compatible interface for local memory system
"""

import json
import sys
import argparse
from typing import Dict, List, Any
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unified_memory_access import unified_memory
from memory_system.services.memory_provider import SQLiteMemoryProvider

class MCPMemoryBridge:
    """Bridge between MCP interface and local memory system"""
    
    def __init__(self, db_path: str = "memory-bank/memory.db"):
        self.unified_memory = unified_memory
        self.db_path = db_path
        print(f"🧠 MCP Memory Bridge initialized with {self.unified_memory.provider_type} provider", file=sys.stderr)
    
    def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP-style requests"""
        method = request.get("method", "")
        params = request.get("params", {})
        
        try:
            if method == "memory/read_graph":
                return self._read_graph()
            elif method == "memory/search_nodes":
                query = params.get("query", "")
                return self._search_nodes(query)
            elif method == "memory/create_entities":
                entities = params.get("entities", [])
                return self._create_entities(entities)
            elif method == "memory/add_observations":
                observations = params.get("observations", [])
                return self._add_observations(observations)
            else:
                return {"error": f"Unknown method: {method}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _read_graph(self) -> Dict[str, Any]:
        """Read memory graph"""
        try:
            # Get session context
            context = self.unified_memory.get_session_context()
            
            # Search for recent memories
            recent_memories = self.unified_memory.search("", limit=20)
            
            graph = {
                "nodes": [],
                "edges": [],
                "session_context": context,
                "total_memories": len(recent_memories)
            }
            
            # Convert memories to nodes
            for i, memory_path in enumerate(recent_memories):
                graph["nodes"].append({
                    "id": f"memory_{i}",
                    "type": "memory",
                    "path": memory_path,
                    "name": Path(memory_path).stem if isinstance(memory_path, str) else f"memory_{i}"
                })
            
            return {"result": graph}
            
        except Exception as e:
            return {"error": f"Failed to read graph: {e}"}
    
    def _search_nodes(self, query: str) -> Dict[str, Any]:
        """Search memory nodes"""
        try:
            results = self.unified_memory.search(query, limit=10)
            
            nodes = []
            for i, memory_path in enumerate(results):
                nodes.append({
                    "id": f"search_{i}",
                    "type": "memory",
                    "path": memory_path,
                    "name": Path(memory_path).stem if isinstance(memory_path, str) else f"result_{i}",
                    "query": query
                })
            
            return {"result": {"nodes": nodes, "query": query, "count": len(nodes)}}
            
        except Exception as e:
            return {"error": f"Search failed: {e}"}
    
    def _create_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create memory entities"""
        try:
            created = []
            
            for entity in entities:
                name = entity.get("name", "unnamed")
                entity_type = entity.get("entityType", "unknown")
                observations = entity.get("observations", [])
                
                # Create memory content
                content = f"# {name}\n\n"
                content += f"**Type:** {entity_type}\n\n"
                content += "**Observations:**\n"
                for obs in observations:
                    content += f"- {obs}\n"
                content += f"\n**Created:** {Path().cwd()}/memory_system/mcp_bridge.py\n"
                
                # Add to memory
                success = self.unified_memory.add(f"entity_{name}", content)
                
                created.append({
                    "name": name,
                    "type": entity_type,
                    "success": success,
                    "observations_count": len(observations)
                })
            
            return {"result": {"created_entities": created, "count": len(created)}}
            
        except Exception as e:
            return {"error": f"Failed to create entities: {e}"}
    
    def _add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add observations to existing entities"""
        try:
            added = []
            
            for obs_group in observations:
                entity_name = obs_group.get("entityName", "unknown")
                contents = obs_group.get("contents", [])
                
                # Search for existing entity
                existing = self.unified_memory.search(entity_name, limit=1)
                
                if existing:
                    # Add observations to existing entity
                    obs_content = f"\n## Additional Observations - {entity_name}\n"
                    for content in contents:
                        obs_content += f"- {content}\n"
                    
                    success = self.unified_memory.add(f"obs_{entity_name}", obs_content)
                else:
                    # Create new entity with observations
                    content = f"# {entity_name}\n\n**Observations:**\n"
                    for content_item in contents:
                        content += f"- {content_item}\n"
                    
                    success = self.unified_memory.add(f"entity_{entity_name}", content)
                
                added.append({
                    "entityName": entity_name,
                    "observations_count": len(contents),
                    "success": success,
                    "was_existing": bool(existing)
                })
            
            return {"result": {"added_observations": added, "count": len(added)}}
            
        except Exception as e:
            return {"error": f"Failed to add observations: {e}"}

def main():
    """Main MCP bridge entry point"""
    parser = argparse.ArgumentParser(description="MCP Memory Bridge")
    parser.add_argument("--db-path", default="memory-bank/memory.db", help="SQLite database path")
    parser.add_argument("--test", action="store_true", help="Run test commands")
    args = parser.parse_args()
    
    bridge = MCPMemoryBridge(args.db_path)
    
    if args.test:
        # Test mode
        print("🧪 Running MCP Memory Bridge tests...")
        
        # Test read_graph
        result = bridge.handle_mcp_request({"method": "memory/read_graph"})
        print(f"Read graph: {result.get('result', {}).get('total_memories', 0)} memories")
        
        # Test search
        result = bridge.handle_mcp_request({
            "method": "memory/search_nodes", 
            "params": {"query": "session"}
        })
        print(f"Search 'session': {result.get('result', {}).get('count', 0)} results")
        
        # Test create entity
        result = bridge.handle_mcp_request({
            "method": "memory/create_entities",
            "params": {
                "entities": [{
                    "name": "mcp_test_entity",
                    "entityType": "test",
                    "observations": ["MCP bridge test", "Local memory integration"]
                }]
            }
        })
        print(f"Create entity: {len(result.get('result', {}).get('created_entities', []))} created")
        
        print("✅ MCP Memory Bridge tests complete!")
        return
    
    # Interactive mode - read JSON requests from stdin
    print("🚀 MCP Memory Bridge started - waiting for requests...", file=sys.stderr)
    
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = bridge.handle_mcp_request(request)
                print(json.dumps(response))
                sys.stdout.flush()
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid JSON request"}))
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("🛑 MCP Memory Bridge stopped", file=sys.stderr)

if __name__ == "__main__":
    main()
