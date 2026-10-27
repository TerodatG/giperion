// Giperion Terminal for VS Code.
// Запускает read-only задачу через локальный API и показывает ответ.

const vscode = require("vscode");

function outputChannel() {
  const channel = vscode.window.createOutputChannel("Giperion");
  channel.show(true);
  return channel;
}

async function runTask() {
  const config = vscode.workspace.getConfiguration("giperion");
  const base = String(config.get("apiUrl") || "http://127.0.0.1:8765").replace(/\/$/, "");
  const token = String(config.get("token") || "").trim();

  if (!token) {
    vscode.window.showErrorMessage(
      "Giperion: укажи giperion.token (python -m tools.agent_api --print-token)."
    );
    return;
  }

  const task = await vscode.window.showInputBox({
    prompt: "Задача для Giperion",
    placeHolder: "Например: где считается бюджет агента?"
  });

  if (!task || !task.trim()) {
    return;
  }

  const channel = outputChannel();
  channel.appendLine(`→ ${task}`);
  channel.appendLine("…");

  try {
    const response = await fetch(`${base}/task`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ task: task.trim(), max_steps: 8, policy: "read" })
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      channel.appendLine(`Ошибка: ${data.error || response.status}`);
      vscode.window.showErrorMessage("Giperion: задача не выполнена.");
      return;
    }

    channel.appendLine(data.answer || "(пустой ответ)");
    channel.appendLine("");
    channel.appendLine(`шагов: ${data.steps}, модель: ${data.model}`);

    for (const step of data.trace || []) {
      channel.appendLine(`  [${step.index}] ${step.kind}: ${step.title}`);
    }

    vscode.window.showInformationMessage("Giperion: готово.");
  } catch (error) {
    channel.appendLine(`Сбой: ${error}`);
    vscode.window.showErrorMessage("Giperion: API недоступен.");
  }
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("giperion.runTask", runTask)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
