"""Replay Observatory app page — direct render without navigation edit."""

from traffictwin.ui.pages.replay_observatory import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
