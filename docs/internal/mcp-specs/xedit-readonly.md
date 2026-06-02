# MCP: xEdit Read-Only

Planned purpose: provide a read-only MCP bridge over the native xEdit outer-client boundary in `tools/mo2-vfs-launcher/xedit-client.ps1`.

The native outer client remains responsible for launching and calling real xEdit automation under the MO2-controlled runtime. This MCP should expose read-only conflict indexing, scoped inspection, and drilldown operations without becoming a separate extraction path.

This MCP should stay focused on agent-facing read-only integration layered on top of that existing native xEdit client boundary.
