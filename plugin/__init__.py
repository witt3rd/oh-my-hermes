"""
OMH Plugin — infrastructure layer for Oh My Hermes skills.

Registers:
  Tools: omh_state, omh_gather_evidence
  Hooks: pre_llm_call, on_session_end
"""


def register(ctx):
    """Entry point called by Hermes plugin discovery."""
    from plugin.tools.state_tool import OMH_STATE_SCHEMA, omh_state_handler
    from plugin.tools.evidence_tool import OMH_EVIDENCE_SCHEMA, omh_evidence_handler
    from plugin.hooks.llm_hooks import pre_llm_call
    from plugin.hooks.session_hooks import on_session_end

    ctx.register_tool("omh_state", OMH_STATE_SCHEMA, omh_state_handler)
    ctx.register_tool("omh_gather_evidence", OMH_EVIDENCE_SCHEMA, omh_evidence_handler)
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("on_session_end", on_session_end)
