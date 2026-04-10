# xedit-cli Contract

## Goals

- orchestrate upstream xEdit without forking it
- run generated Pascal scripts
- normalize output for agent consumption

## Read-Only Commands

- list masters
- inspect records
- scan overrides
- export filtered conflict reports

## Future Write Commands

- create compatibility patch shells
- apply controlled scripted edits to a new patch plugin

## Safety Rules

- never edit source mods in place
- default to read-only mode
- require explicit patch targets for write operations
