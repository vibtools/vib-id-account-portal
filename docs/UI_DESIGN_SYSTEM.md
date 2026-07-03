# Vib ID Portal UI Design System — v1.1.0

## Direction

The account portal follows the Vib Tools Open Source Hub visual language and applies it to a high-density identity-management workflow. The implementation combines repository-oriented navigation, Linear-style typography and pace, Vercel-like management clarity, Cloudflare-like settings density, and Figma-like navigation consistency.

## Design principles

- Flat: surfaces are separated primarily by border, tone, and spacing.
- Clean: decorative effects never compete with identity or security data.
- Fast: server-rendered HTML, local assets, and framework-free JavaScript.
- Keyboard friendly: visible focus rings, command palette, predictable tab order, and Escape handling.
- Developer first: monospace metadata, dense tables, explicit states, and low-friction navigation.
- Responsive: the same information architecture adapts to desktop, tablet, and mobile without horizontal overflow.

## Core tokens

| Token | Dark value | Light value | Purpose |
|---|---|---|---|
| Background | `#0D1117` | `#F6F8FA` | Application canvas |
| Surface | `#161B22` | `#FFFFFF` | Cards, panels, navigation |
| Border | `#30363D` | `#D0D7DE` | Separation and control outlines |
| Primary | `#2563EB` | `#2563EB` | Primary actions and active states |
| Secondary | `#38BDF8` | `#0284C7` | Links, metadata, informational accents |
| Primary text | `#F8FAFC` | `#0D1117` | Main content |
| Secondary text | `#8B949E` | `#57606A` | Supporting content |
| Success | `#22C55E` | `#15803D` | Verified and healthy states |
| Warning | `#F59E0B` | `#B45309` | Attention states |
| Danger | `#EF4444` | `#DC2626` | Destructive actions and errors |
| Info | `#8B5CF6` | `#7C3AED` | Informational status |

## Typography

- Interface: Inter-compatible local system stack
- Technical metadata: JetBrains Mono-compatible monospace stack
- Page headings use a compact responsive scale, not oversized marketing typography.
- Labels and status metadata use small, legible sizes with deliberate letter spacing.

## Components

- Top bar: brand, page context, global command search, appearance access, and account actions.
- Sidebar: persistent desktop navigation; modal drawer on compact screens.
- Panels: one-pixel borders, moderate radius, no persistent heavy shadow.
- Forms: clear labels, 44px minimum interactive height, visible error text and focus treatment.
- Tables: dense rows, responsive containment, readable status badges, and monospace references.
- Command palette: searchable route/action list with keyboard selection.
- Status badges: semantic color plus text; color is never the only signal.

## Brand asset replacement

Replace only the five files under `app/static/brand/`. Do not change the filenames. Templates contain intrinsic dimensions to prevent layout shifts, and JavaScript provides a text fallback when an image fails to load.
