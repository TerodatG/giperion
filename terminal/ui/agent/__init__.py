# Giperion/terminal/ui/agent/__init__.py                               v001
# Окно агента: панели управления, подтверждения и лента шагов.
# Последнее изменение: пакет выделен из agent_dialog.

from terminal.ui.agent.approval import ApprovalPanel
from terminal.ui.agent.controls import AgentControls
from terminal.ui.agent.dialog import AgentDialog, show_agent_dialog
from terminal.ui.agent.trace import AgentTrace
from terminal.ui.agent.worktree_bar import WorktreeBar

__all__ = [
    "AgentControls",
    "AgentDialog",
    "AgentTrace",
    "ApprovalPanel",
    "WorktreeBar",
    "show_agent_dialog",
]
