# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-11-12

### Added
- 🎯 Natural language test generation using Google ADK
- 🔄 Self-healing selectors with HTML context extraction
- 📊 Rich HTML/JSON reporting with screenshots and videos
- 🤖 Multi-mode execution (Function Tools, Natural Language, Computer Use)
- ⚡ Adaptive timeout system based on execution history
- 🔍 Smart DOM analysis with HTML snippet extraction
- 📝 Comprehensive test scenario examples
- 🧪 Demo pages (login and e-commerce)

### Changed
- Replaced multi-agent orchestration with single-agent approach for better reliability
- Improved DOM context from JSON to HTML snippets for better selector extraction
- Enhanced agent instructions with explicit selector priority rules
- Increased DOM context limit from 4K to 12K characters

### Fixed
- ADK template variable parsing errors
- Selector generation issues with dynamic IDs
- Feedback loop degrading scenario quality
- Placeholder selector reliability issues

### Technical Improvements
- DOM caching (5-minute TTL) to reduce redundant captures
- Async exception handling in ADK agent
- Smart JSON extraction with scoring algorithm
- Selector normalization for consistent matching
- Warnings suppression for ADK SDK messages

## [0.1.0] - Initial Release

### Added
- Basic Playwright test execution
- YAML scenario support
- Simple reporting
- Computer Use mode (experimental)
