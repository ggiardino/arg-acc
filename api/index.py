"""Aplicación FastAPI de ar-acc optimizada para Vercel Serverless.

Expone:
  - GET  /            -> interfaz web (chat/dashboard) con Tailwind CSS por CDN.
  - POST /api/chat    -> consulta el grafo de corrupción vía GraphCypherQAChain.
  - GET  /api/health  -> verificación rápida de estado.

Vercel detecta automáticamente la variable ASGI `app`.
"""

from __future__ import annotations

import pathlib
import sys

# Agrega la raíz del proyecto al path para resolver `agent` y `config`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agent import query_corruption_graph  # noqa: E402
from config.settings import settings  # noqa: E402
from dashboard.web import router as dashboard_router  # noqa: E402

app = FastAPI(title="ar-acc", description="Investigación de corrupción sobre grafos")
app.include_router(dashboard_router)


class ChatRequest(BaseModel):
    """Cuerpo del endpoint /api/chat."""
    question: str = Field(..., min_length=1, description="Pregunta en lenguaje natural")
    provider: str | None = Field(None, description="openai | groq | anthropic")
    api_key: str | None = Field(None, description="API Key opcional del cliente")


@app.get("/api/health")
def health() -> dict:
    """Estado del servicio y proveedor de IA configurado por defecto."""
    return {"status": "ok", "provider": settings.llm_provider}


@app.post("/api/chat")
def chat(payload: ChatRequest) -> JSONResponse:
    """Recibe la pregunta y devuelve la respuesta analítica del grafo."""
    answer = query_corruption_graph(
        payload.question,
        provider=payload.provider,
        api_key=payload.api_key,
    )
    return JSONResponse({"answer": answer})


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Interfaz web responsiva para consultar el grafo desde el navegador."""
    return HTMLResponse(INDEX_HTML)


INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ar-acc · Investigación de corrupción</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 text-slate-800 min-h-screen flex flex-col">
  <header class="bg-slate-900 text-white">
    <div class="max-w-3xl mx-auto px-4 py-5">
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <span>🔎</span> ar-acc
      </h1>
      <p class="text-slate-300 text-sm mt-1">
        Réplica argentina y ligera del framework acc/bro de OCCRP.
        Consultá el grafo de corrupción en lenguaje natural.
      </p>
      <a href="/dashboard"
        class="inline-block mt-3 text-sm bg-slate-700 hover:bg-slate-600
               text-white rounded-lg px-4 py-1.5 transition">
        Abrir el dashboard de inconsistencias en DDJJ &rarr;
      </a>
    </div>
  </header>

  <main class="flex-1 max-w-3xl w-full mx-auto px-4 py-6">
    <div class="bg-white rounded-xl shadow p-4 mb-4">
      <div class="grid sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-semibold text-slate-500 mb-1">
            Proveedor de IA
          </label>
          <select id="provider"
            class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                   focus:outline-none focus:ring-2 focus:ring-slate-400">
            <option value="">Predeterminado (.env)</option>
            <option value="openai">OpenAI</option>
            <option value="groq">Groq</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-500 mb-1">
            API Key (opcional)
          </label>
          <input id="apikey" type="password" placeholder="Se usa la del .env si está vacía"
            class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                   focus:outline-none focus:ring-2 focus:ring-slate-400" />
        </div>
      </div>
    </div>

    <div id="chat" class="space-y-3 mb-4"></div>

    <div class="bg-white rounded-xl shadow p-3 sticky bottom-4">
      <div class="flex gap-2">
        <input id="question" type="text" autocomplete="off"
          placeholder="Ej: ¿Qué funcionarios viajaron a paraísos fiscales?"
          class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm
                 focus:outline-none focus:ring-2 focus:ring-slate-400" />
        <button id="send"
          class="bg-slate-900 hover:bg-slate-700 text-white text-sm font-semibold
                 rounded-lg px-5 py-2 transition disabled:opacity-50">
          Consultar
        </button>
      </div>
      <div class="mt-2 flex flex-wrap gap-2" id="examples"></div>
    </div>
  </main>

  <footer class="text-center text-xs text-slate-400 py-4">
    ar-acc — datos simulados con fines de auditoría y educación.
  </footer>

  <script>
    const chat = document.getElementById("chat");
    const input = document.getElementById("question");
    const sendBtn = document.getElementById("send");
    const examplesBox = document.getElementById("examples");

    const examples = [
      "¿Qué funcionarios tienen un patrimonio desproporcionado respecto de sus ingresos?",
      "¿Qué empresas ganaron más de un contrato del Estado?",
      "¿Qué funcionarios viajaron a paraísos fiscales como las Islas Caimán o Andorra?"
    ];

    examples.forEach(function (ex) {
      const chip = document.createElement("button");
      chip.textContent = ex;
      chip.className =
        "text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full px-3 py-1";
      chip.onclick = function () { input.value = ex; input.focus(); };
      examplesBox.appendChild(chip);
    });

    function bubble(text, role) {
      const wrap = document.createElement("div");
      wrap.className = role === "user" ? "flex justify-end" : "flex justify-start";
      const box = document.createElement("div");
      box.className =
        (role === "user"
          ? "bg-slate-900 text-white"
          : "bg-white text-slate-800 border border-slate-200") +
        " rounded-xl px-4 py-3 max-w-[85%] text-sm whitespace-pre-wrap shadow-sm";
      box.textContent = text;
      wrap.appendChild(box);
      chat.appendChild(wrap);
      window.scrollTo(0, document.body.scrollHeight);
      return box;
    }

    async function ask() {
      const question = input.value.trim();
      if (!question) return;
      input.value = "";
      bubble(question, "user");
      const pending = bubble("Consultando el grafo...", "assistant");
      sendBtn.disabled = true;
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: question,
            provider: document.getElementById("provider").value || null,
            api_key: document.getElementById("apikey").value || null
          })
        });
        const data = await res.json();
        pending.textContent = data.answer || "Sin respuesta.";
      } catch (err) {
        pending.textContent = "Error de conexión: " + err;
      } finally {
        sendBtn.disabled = false;
      }
    }

    sendBtn.onclick = ask;
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") ask();
    });
  </script>
</body>
</html>
"""
