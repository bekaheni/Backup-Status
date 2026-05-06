# Bekat IT — Standard Design System v1.0

> **Scope:** This standard applies to all Bekat IT internal tools and projects. Any new project should use these tokens as its starting point.

---

## Sidebar and Header

| Token | Value |
|---|---|
| Background colour | `#1E2328` |
| Active nav item background | `rgba(255, 255, 255, 0.12)` |
| Active nav item text | `#FFFFFF` (full white) |
| Inactive nav item text | `rgba(255, 255, 255, 0.65)` |
| Inactive nav item text (hover) | `#FFFFFF` (full white) |
| Dividers / borders | `rgba(255, 255, 255, 0.10)` |
| Sidebar width — expanded | `220px` |
| Sidebar width — collapsed | `60px` (icons only) |

The fixed top header bar uses the same `#1E2328` background to form a unified chrome across the top and left of the viewport.

---

## Content Area

| Token | Value |
|---|---|
| Page background | `#F4F6F9` |
| Card background | `#FFFFFF` |
| Card border colour | `#E5E9EF` |
| Card border radius | `8px` |

Cards use `border: 1px solid #E5E9EF` and `border-radius: 8px`. No box-shadow is required by default; subtle shadow may be added for elevated / modal contexts.

---

## Typography

| Token | Value |
|---|---|
| Font family | `'Inter', system-ui, -apple-system, sans-serif` |
| Primary text colour | `#1E2328` |
| Muted text colour | `#6B7280` |

Inter should be loaded from Google Fonts or bundled locally. The system-font fallback ensures readable text before Inter loads.

---

## Status Colours

| Role | Hex |
|---|---|
| Success | `#16A34A` |
| Warning | `#D97706` |
| Danger | `#DC2626` |
| Accent / Info | `#2563EB` |

Use these colours for badges, alert banners, chart series, and any other status-indicating UI elements. Do not substitute custom colours for these roles.

---

## Spacing

Base unit: **4px**

| Name | Value |
|---|---|
| xs | `4px` |
| sm | `8px` |
| md | `12px` |
| lg | `16px` |
| xl | `24px` |
| 2xl | `32px` |

All margins, paddings, and gaps should use multiples of the 4px base unit. The values above cover the most common use cases.

---

## Icons

All projects use the **Bootstrap Icons** library for consistency. Import via CDN or npm package `bootstrap-icons`. Do not mix in other icon sets (e.g. Font Awesome, Material Icons) within the same project.

---

## Navigation

All projects follow the same navigation pattern:

- **Layout:** Collapsible left sidebar + fixed top header bar.
- **Desktop collapsed state:** Sidebar shrinks to `60px` and shows icons only; tooltips display the item label on hover.
- **Desktop expanded state:** Sidebar is `220px` wide and shows icon + label.
- **Mobile:** Sidebar is hidden by default. It slides in as a full-height overlay with a dark semi-transparent backdrop (`rgba(0,0,0,0.5)`). Tapping the backdrop closes the sidebar.
- **Persistence:** Collapse state (expanded / collapsed) is stored in `localStorage` under a project-specific key (e.g. `coresight_sidebar_collapsed`) so the user's preference survives page reloads.

---

## Projects

The following projects currently implement this design standard:

| Project | Status |
|---|---|
| **CoreSight Backup Status** | Active — fully adopted v1.0 |
| **IMS** | Active — fully adopted v1.0 |

> **Planned:** The Server Up/Down dashboard is scheduled to adopt this standard in a future update.

---

*Bekat IT — Design System v1.0*
