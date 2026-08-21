from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp_server.database import db_search_open_tickets
from mcp_server.runtime_tools import list_all_agents, list_tools, set_tool_enabled
from state_graph.common.store import StateStore


class PlatformApp:
    def __init__(self, db_path: str = "db/support.db"):
        self.store = StateStore(db_path)
        self.agents = [
            {
                "name": "support_ticket_mcp",
                "label": "Support Ticket MCP",
                "description": "Handles ticket lookup, status updates, and dashboard summaries.",
            },
            {
                "name": "memory_rag_agent",
                "label": "Memory/RAG Agent",
                "description": "Answers grounded knowledge questions with retrieval and memory.",
            },
            {
                "name": "planning_agent",
                "label": "Planning Agent",
                "description": "Breaks multi-step goals into actionable plans.",
            },
            {
                "name": "state_graph_agent",
                "label": "State Graph Agent",
                "description": "Runs the durable state-graph workflows and escalations.",
            },
        ]

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {
                **agent,
                "tools": list_tools(agent["name"]),
            }
            for agent in self.agents
        ]

    def toggle_tool(self, agent_name: str, tool_name: str, enabled: bool) -> dict[str, Any]:
        set_tool_enabled(agent_name, tool_name, enabled)
        self.store.set_agent_tool(agent_name, tool_name, enabled)
        return {"agent": agent_name, "tool": tool_name, "enabled": enabled}

    def list_tools_for_agent(self, agent_name: str) -> list[str]:
        saved = self.store.list_agent_tools(agent_name)
        if saved:
            return saved
        return list_tools(agent_name)

    def add_document(self, title: str, content: str) -> dict[str, Any]:
        document_id = self.store.add_rag_document(title, content, source="platform")
        return {"document_id": document_id, "title": title, "source": "platform"}

    def list_documents(self) -> list[dict[str, Any]]:
        return self.store.list_rag_documents()

    def list_hitl_tasks(self) -> list[dict[str, Any]]:
        return self.store.list_pending_hitl()

    def resolve_hitl(self, task_id: str, decision: str, admin_id: str) -> dict[str, Any]:
        from state_graph.graphs.sla_breach_escalation import resolve_sla_breach_hitl
        from state_graph.graphs.claim_appeal import resolve_claim_hitl

        task = self.store.get_hitl_task(task_id)
        if task is None:
            return {"success": False, "error": "task-not-found"}

        run_id = task["run_id"]
        graph_name = self.store.get_run(run_id)
        if graph_name is not None:
            graph_name = graph_name.get("graph_name")

        if graph_name == "sla_breach_escalation":
            result = resolve_sla_breach_hitl(task_id, decision, admin_id, db_path="db/support.db")
        elif graph_name == "claim_appeal":
            result = resolve_claim_hitl(task_id, decision, admin_id, db_path="db/support.db")
        else:
            self.store.resolve_hitl_task(task_id, decision, admin_id)
            result = "RESOLVED"

        return {"success": True, "result": result, "task_id": task_id, "decision": decision}

    def list_failures(self) -> list[dict[str, Any]]:
        return self.store.list_failure_tickets(status="OPEN") + self.store.list_failure_tickets(status="INVESTIGATING")

    def resolve_failure(self, failure_id: str, resolution: str, admin_id: str) -> dict[str, Any]:
        from state_graph.graphs.sla_breach_escalation import resume_sla_breach_after_failure
        from state_graph.graphs.claim_appeal import resume_claim_after_failure

        failure = self.store.list_failure_tickets()
        match = next((item for item in failure if item["failure_id"] == failure_id), None)
        if match is None:
            return {"success": False, "error": "failure-not-found"}

        run_id = match["run_id"]
        run = self.store.get_run(run_id)
        graph_name = run.get("graph_name") if run else None

        if graph_name == "sla_breach_escalation":
            result = resume_sla_breach_after_failure(failure_id, resolution, admin_id, db_path="db/support.db")
        elif graph_name == "claim_appeal":
            result = resume_claim_after_failure(failure_id, resolution, admin_id, db_path="db/support.db")
        else:
            self.store.resolve_failure(failure_id, resolution, admin_id)
            result = "RESOLVED"

        return {"success": True, "result": result, "failure_id": failure_id}

    def send_chat(self, agent_name: str, user_id: str, message: str) -> dict[str, Any]:
        self.store.save_chat_message(agent_name, user_id, "user", message)
        response = self._generate_agent_reply(agent_name, message)
        self.store.save_chat_message(agent_name, user_id, "assistant", response)
        return {"agent": agent_name, "user_id": user_id, "reply": response}

    def _generate_agent_reply(self, agent_name: str, message: str) -> str:
        normalized = (message or "").strip().lower()

        if agent_name == "support_ticket_mcp":
            if "open" in normalized and "ticket" in normalized:
                tickets = db_search_open_tickets()
                if not tickets:
                    return "There are no open tickets right now."
                top = tickets[0]
                return f"The most urgent open ticket is #{top['ticket_id']} for {top['customer_name']}: {top['issue']} (priority {top['priority']})."
            return "Support Ticket MCP is active. I can look up tickets, search by team, or summarize open work."

        if agent_name == "memory_rag_agent":
            docs = self.store.list_rag_documents()
            if docs:
                title = docs[0]["title"]
                return f"The RAG agent has {len(docs)} grounded documents loaded, including '{title}'."
            return "The RAG agent is ready; no documents are loaded yet. Add one from the admin panel."

        if agent_name == "planning_agent":
            if "ticket" in normalized or "issue" in normalized:
                return "Plan: 1) identify the root issue, 2) collect required facts, 3) choose the least risky remediation, 4) verify with the support workflow."
            return "Planning agent is live. I can decompose the request into a short, ordered execution plan."

        if agent_name == "state_graph_agent":
            if "claim" in normalized or "appeal" in normalized:
                return "State Graph agent is ready for a claim-appeal workflow. It can pause for admin approval, persist the run, and resume after the external decision."
            if "sla" in normalized or "breach" in normalized:
                return "State Graph agent is ready for SLA breach escalation. It detects the breach, grounds policy evidence, and pauses for HITL when the decision exceeds policy limits."
            return "State Graph agent is active. I can execute the durable state-graph workflows and monitor HITL or failure tickets."

        return "Agent is ready to help."

    def chat_history(self, agent_name: str, user_id: str | None = None) -> list[dict[str, Any]]:
        return self.store.list_chat_messages(agent_name, user_id, limit=25)


def create_app(db_path: str = "db/support.db") -> PlatformApp:
    return PlatformApp(db_path=db_path)


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str, status: int = 200) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _index_html() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Support Ticket Platform</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
          .wrapper { display: flex; min-height: 100vh; }
          .sidebar { width: 260px; background: #111827; padding: 20px; border-right: 1px solid #334155; }
          .main { flex: 1; padding: 20px; }
          .panel { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
          label { display: block; margin: 8px 0 4px; font-size: 12px; color: #cbd5e1; }
          select, input, textarea, button { width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; }
          button { background: #2563eb; cursor: pointer; }
          .chat-area { min-height: 220px; max-height: 260px; overflow: auto; background: rgba(15,23,42,0.9); border: 1px solid #334155; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
          .row { display: flex; gap: 12px; }
          .box { flex: 1; }
          .small { font-size: 12px; color: #cbd5e1; }
        </style>
      </head>
      <body>
        <div class="wrapper">
          <aside class="sidebar">
            <h2>Agents</h2>
            <div id="agent-list" class="small"></div>
            <div class="panel">
              <label for="agentSelect">Selected agent</label>
              <select id="agentSelect"></select>
            </div>
          </aside>
          <main class="main">
            <div class="panel">
              <h2>User Chat</h2>
              <div id="chatArea" class="chat-area"></div>
              <label for="chatInput">Message</label>
              <textarea id="chatInput" rows="3" placeholder="Ask the selected agent..."></textarea>
              <div style="margin-top:12px"><button id="sendChat">Send</button></div>
            </div>
            <div class="row">
              <div class="box panel">
                <h3>Admin: Tools</h3>
                <div id="toolList"></div>
              </div>
              <div class="box panel">
                <h3>Admin: RAG Documents</h3>
                <div id="ragList"></div>
                <label for="docTitle">Title</label>
                <input id="docTitle" placeholder="Document title">
                <label for="docContent">Content</label>
                <textarea id="docContent" rows="3" placeholder="Paste the knowledge document"></textarea>
                <div style="margin-top:12px"><button id="addDoc">Add document</button></div>
              </div>
            </div>
            <div class="row">
              <div class="box panel">
                <h3>Admin: HITL tasks</h3>
                <div id="hitlList"></div>
              </div>
              <div class="box panel">
                <h3>Admin: Failure tickets</h3>
                <div id="failureList"></div>
              </div>
            </div>
          </main>
        </div>
        <script>
          const state = { agent: 'support_ticket_mcp', userId: 'web-user' };
          async function fetchJson(url, method='GET', body=null) {
            const options = { method, headers: {'Content-Type': 'application/json'} };
            if (body) options.body = JSON.stringify(body);
            const res = await fetch(url, options);
            return await res.json();
          }
          function renderAgentList(agents) {
            const list = document.getElementById('agent-list');
            const select = document.getElementById('agentSelect');
            list.innerHTML = agents.map(a => `<div style="margin-bottom:8px"><strong>${a.label}</strong><div class="small">${a.description}</div></div>`).join('');
            select.innerHTML = agents.map(a => `<option value="${a.name}">${a.label}</option>`).join('');
            select.value = state.agent;
          }
          function renderChat(messages) {
            const area = document.getElementById('chatArea');
            area.innerHTML = messages.map(m => `<div style="margin-bottom:12px"><strong>${m.role === 'user' ? 'You' : 'Agent'}:</strong> ${m.message}</div>`).join('');
            area.scrollTop = area.scrollHeight;
          }
          async function loadAgents() {
            const agents = await fetchJson('/api/agents');
            renderAgentList(agents);
            state.agent = document.getElementById('agentSelect').value;
            loadChat();
            loadAdmin();
          }
          async function loadChat() {
            const history = await fetchJson(`/api/chat/history?agent=${encodeURIComponent(state.agent)}&user_id=${encodeURIComponent(state.userId)}`);
            renderChat(history);
          }
          async function loadAdmin() {
            const tools = await fetchJson(`/api/admin/tools?agent=${encodeURIComponent(state.agent)}`);
            const docs = await fetchJson('/api/admin/rag');
            const hitl = await fetchJson('/api/admin/hitl');
            const failures = await fetchJson('/api/admin/failures');
            const toolContainer = document.getElementById('toolList');
            toolContainer.innerHTML = tools.map(tool => `<div style="margin-bottom:8px"><label><input type="checkbox" data-tool="${tool}" ${tool.enabled ? 'checked' : ''}> ${tool.name}</label></div>`).join('');
            toolContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
              cb.addEventListener('change', async () => {
                const body = { agent: state.agent, tool: cb.dataset.tool, enabled: cb.checked };
                await fetchJson('/api/admin/tools', 'POST', body);
                loadAdmin();
              });
            });
            document.getElementById('ragList').innerHTML = docs.map(d => `<div style="margin-bottom:8px"><strong>${d.title}</strong><div class="small">${d.source}</div></div>`).join('') || '<div class="small">No documents yet.</div>';
            document.getElementById('hitlList').innerHTML = hitl.length ? hitl.map(task => `<div style="margin-bottom:8px"><strong>${task.task_id.slice(0,8)}</strong><div class="small">${task.reason}</div><button data-hitl="${task.task_id}" data-decision="approve">Approve</button><button data-hitl="${task.task_id}" data-decision="reject">Reject</button></div>`).join('') : '<div class="small">No pending HITL tasks.</div>';
            document.getElementById('hitlList').querySelectorAll('button[data-hitl]').forEach(btn => {
              btn.addEventListener('click', async () => {
                await fetchJson(`/api/admin/hitl/${btn.dataset.hitl}/resolve`, 'POST', { decision: btn.dataset.decision, admin_id: 'admin-web' });
                loadAdmin();
              });
            });
            document.getElementById('failureList').innerHTML = failures.length ? failures.map(f => `<div style="margin-bottom:8px"><strong>${f.node_name}</strong><div class="small">${f.error_message}</div><button data-failure="${f.failure_id}">Resolve</button></div>`).join('') : '<div class="small">No open failure tickets.</div>';
            document.getElementById('failureList').querySelectorAll('button[data-failure]').forEach(btn => {
              btn.addEventListener('click', async () => {
                await fetchJson(`/api/admin/failures/${btn.dataset.failure}/resolve`, 'POST', { resolution: 'Resolved by platform admin', admin_id: 'admin-web' });
                loadAdmin();
              });
            });
          }
          document.getElementById('agentSelect').addEventListener('change', function() {
            state.agent = this.value;
            loadChat();
            loadAdmin();
          });
          document.getElementById('sendChat').addEventListener('click', async function() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (!message) return;
            const response = await fetchJson('/api/chat', 'POST', { agent: state.agent, user_id: state.userId, message });
            input.value = '';
            loadChat();
          });
          document.getElementById('addDoc').addEventListener('click', async function() {
            const title = document.getElementById('docTitle').value.trim();
            const content = document.getElementById('docContent').value.trim();
            if (!title || !content) return;
            await fetchJson('/api/admin/rag', 'POST', { title, content });
            document.getElementById('docTitle').value = '';
            document.getElementById('docContent').value = '';
            loadAdmin();
          });
          loadAgents();
        </script>
      </body>
    </html>
    """


class PlatformHandler(BaseHTTPRequestHandler):
    app: PlatformApp | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            _html_response(self, _index_html())
            return

        if path == "/api/agents":
            _json_response(self, self.app.list_agents())
            return

        if path == "/api/admin/tools":
            agent_name = query.get("agent", ["support_ticket_mcp"])[0]
            tool_names = self.app.list_tools_for_agent(agent_name)
            response = [{"name": name, "enabled": True} for name in tool_names]
            _json_response(self, response)
            return

        if path == "/api/admin/rag":
            _json_response(self, self.app.list_documents())
            return

        if path == "/api/admin/hitl":
            _json_response(self, self.app.list_hitl_tasks())
            return

        if path == "/api/admin/failures":
            _json_response(self, self.app.list_failures())
            return

        if path.startswith("/api/chat/history"):
            agent_name = query.get("agent", ["support_ticket_mcp"])[0]
            user_id = query.get("user_id", ["web-user"])[0]
            _json_response(self, self.app.chat_history(agent_name, user_id))
            return

        _json_response(self, {"error": "not-found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            payload = {}

        if path == "/api/chat":
            agent_name = payload.get("agent", "support_ticket_mcp")
            user_id = payload.get("user_id", "web-user")
            message = payload.get("message", "")
            _json_response(self, self.app.send_chat(agent_name, user_id, message))
            return

        if path == "/api/admin/tools":
            agent_name = payload.get("agent", "support_ticket_mcp")
            tool_name = payload.get("tool", "")
            enabled = bool(payload.get("enabled", True))
            _json_response(self, self.app.toggle_tool(agent_name, tool_name, enabled))
            return

        if path == "/api/admin/rag":
            title = payload.get("title", "Uploaded document")
            content = payload.get("content", "")
            _json_response(self, self.app.add_document(title, content))
            return

        if path.startswith("/api/admin/hitl/") and path.endswith("/resolve"):
            task_id = path.split("/api/admin/hitl/")[1].rsplit("/resolve", 1)[0]
            decision = payload.get("decision", "approve")
            admin_id = payload.get("admin_id", "admin-web")
            _json_response(self, self.app.resolve_hitl(task_id, decision, admin_id))
            return

        if path.startswith("/api/admin/failures/") and path.endswith("/resolve"):
            failure_id = path.split("/api/admin/failures/")[1].rsplit("/resolve", 1)[0]
            resolution = payload.get("resolution", "Resolved by admin")
            admin_id = payload.get("admin_id", "admin-web")
            _json_response(self, self.app.resolve_failure(failure_id, resolution, admin_id))
            return

        _json_response(self, {"error": "not-found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8001, db_path: str = "db/support.db") -> None:
    app = PlatformApp(db_path=db_path)
    PlatformHandler.app = app
    server = ThreadingHTTPServer((host, port), PlatformHandler)
    print(f"Platform running on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
