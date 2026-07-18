# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal testing/dummy project for the Claude Code CLI. It contains only the `@anthropic-ai/claude-code` npm package as a dependency with no application-specific code, tests, or build system.

## Common Commands

Since this is primarily a dependency container with no build system:

- **Install dependencies**: `npm install`
- **View Claude Code version**: `npx claude --version`
- **Run Claude Code**: `npx claude` (from the project root or globally if installed)

## Project Structure

- `package.json` — Defines the project dependencies
- `node_modules/` — Contains the Claude Code CLI and its dependencies

## Key Notes

- This repository does not contain application-specific code, tests, or complex architecture
- It serves as a lightweight wrapper or testing environment for the Claude Code CLI tool
- For Claude Code documentation and capabilities, refer to the bundled README at `node_modules/@anthropic-ai/claude-code/README.md`
