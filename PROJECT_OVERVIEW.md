# CRO Website — Full Project Overview
> **Purpose of this document:** This file is intended to give a complete and detailed picture of the existing CRO (Climate Resilience Observatory) website to any AI agent or developer who needs to recreate or extend it as a new website. Every section covers structure, content, and design intent.

---

## 1. Project Identity

| Property        | Value                                                                 |
|-----------------|-----------------------------------------------------------------------|
| **Full Name**   | Climate Resilience Observatory (CRO)                                  |
| **Tagline**     | Data-driven disaster risk reduction & climate resilience analysis     |
| **Copyright**   | © 2025 Climate Resilience Observatory — IIIT Lucknow                 |
| **Motto**       | "Data-driven resilience for a sustainable future"                    |
| **Partners**    | IIIT Lucknow, UP Relief Commissioner's Office                        |

---

## 2. Tech Stack

| Layer            | Technology                                                                 |
|------------------|----------------------------------------------------------------------------|
| **Framework**    | React 18 (TypeScript, `.tsx`)                                              |
| **Build Tool**   | Vite 5                                                                     |
| **Styling**      | Tailwind CSS v3 + custom theme tokens (`un-blue`, `un-dark-gray`, etc.)    |
| **UI Components**| shadcn/ui (Radix UI primitives)                                            |
| **Routing**      | React Router DOM v6                                                        |
| **Animation**    | Framer Motion                                                              |
| **Icons**        | Lucide React                                                               |
| **Forms**        | React Hook Form + Zod                                                      |
| **Charts**       | Recharts                                                                   |
| **Notifications**| Sonner + Radix Toast                                                       |
| **Dev Language** | TypeScript 5                                                               |
| **Package Mgr**  | npm (also has bun.lockb)                                                   |

### Key npm Scripts
```
npm run dev       → Start development server (Vite)
npm run build     → Production build
npm run preview   → Preview production build
npm run lint      → ESLint check
```
---

## 3. Folder / File Tree

```
crowebsite/
├── index.html                    ← App entry point (Vite HTML shell)
├── package.json                  ← Dependencies and scripts
├── vite.config.ts                ← Vite configuration
├── tailwind.config.ts            ← Tailwind custom theme
├── tsconfig.json                 ← TypeScript config
├── tsconfig.app.json
├── tsconfig.node.json
├── postcss.config.js
├── eslint.config.js
├── components.json               ← shadcn/ui component registry config
├── start.bat                     ← Windows batch script to start project
├── .gitignore
├── bun.lockb                     ← Bun lockfile
├── README.md                     ← Original readme
│
├── public/                       ← Static assets (served as-is)
│   ├── favicon.png               ← Browser tab icon
│   ├── placeholder.svg           ← Generic placeholder image
│   ├── robots.txt                ← SEO crawling rules
│   └── team-photos/              ← Team member profile images (PNG)
│       ├── Aishrica.png
│       ├── Arjun.png
│       ├── Debayan.png
│       ├── Gunjan.png
│       ├── Harsh.png
│       ├── Kamal.png
│       ├── Manas.png
│       ├── Rohit.png
│       ├── Rupsa.png
│       ├── Shiva.png
│       ├── Sunil.png
│       ├── Tarun.png
│       ├── Urmilla.png
│       ├── laxmikant.png
│       ├── samir.png
│       └── sridip-basu.png
│
├── src/
│   ├── main.tsx                  ← React DOM root render
│   ├── App.tsx                   ← Router setup + top-level component tree
│   ├── App.css                   ← App-level CSS overrides
│   ├── index.css                 ← Global styles, Tailwind base
│   ├── vite-env.d.ts             ← Vite env type declarations
│   │
│   ├── assets/                   ← Bundled image assets (imported in code)
│   │   ├── cro-logo.jpg          ← Main CRO logo (shown in header)
│   │   ├── iiitl-logo.png        ← IIIT Lucknow logo
│   │   ├── govt-up-logo.png      ← Govt. of UP logo
│   │   └── relief-commissioner-logo.jpg ← UP Relief Commissioner's Office logo
│   │
│   ├── components/
│   │   ├── Layout.tsx            ← Shared page wrapper (Header + Nav + Footer)
│   │   ├── NavLink.tsx           ← Reusable styled navigation link
│   │   └── ui/                   ← All shadcn/ui components (49 files)
│   │       (accordion, alert, avatar, badge, button, calendar, card,
│   │        carousel, chart, checkbox, collapsible, command, context-menu,
│   │        dialog, drawer, dropdown-menu, form, hover-card, input,
│   │        input-otp, label, menubar, navigation-menu, pagination,
│   │        popover, progress, radio-group, resizable, scroll-area,
│   │        select, separator, sheet, sidebar, skeleton, slider, sonner,
│   │        switch, table, tabs, textarea, toast, toaster, toggle,
│   │        toggle-group, tooltip, use-sidebar)
│   │
│   ├── hooks/
│   │   ├── use-mobile.tsx        ← Hook to detect mobile viewport
│   │   └── use-toast.ts          ← Toast notification state hook
│   │
│   ├── lib/
│   │   └── utils.ts              ← Tailwind class merging utility (clsx + tailwind-merge)
│   │
│   └── pages/
│       ├── Home.tsx              ← Homepage (route: "/")
│       ├── About.tsx             ← About page (route: "/about")
│       ├── Projects.tsx          ← Projects/Work page (route: "/projects")
│       ├── Team.tsx              ← Team page (route: "/team")
│       └── NotFound.tsx          ← 404 fallback (route: "*")
│
└── backend/
    └── venv/                     ← Python virtual environment (backend placeholder)
```

---

## 4. Routing Map

| URL Path     | Component         | Description                          |
|--------------|-------------------|--------------------------------------|
| `/`          | `Home.tsx`        | Landing / hero page                  |
| `/about`     | `About.tsx`       | About the Observatory                |
| `/projects`  | `Projects.tsx`    | Current & archived research projects |
| `/team`      | `Team.tsx`        | Team member directory                |
| `/involved`  | *(not yet built)* | "Get Involved" CTA — link exists in nav, no page yet |
| `*`          | `NotFound.tsx`    | 404 page                             |

---

## 5. Global Layout (`src/components/Layout.tsx`)

The `Layout` component wraps every page with a **header**, **sticky navigation bar**, **main content slot**, and a **footer**.

### Header
- **CRO Logo** (`cro-logo.jpg`) on the left
- **Site Title**: "Climate Resilience Observatory" in large bold text
- **Sub-tagline on right** (desktop only): *"Data-driven disaster risk reduction & climate resilience analysis"*

### Navigation Bar (sticky, dark gray background)
Links in order:
1. 🏠 Home icon → `/`
2. About Us → `/about`
3. Our Work → `/projects`
4. Team → `/team`
5. Get Involved → `/involved` *(no page yet)*

Mobile: hamburger icon (☰) toggles a dropdown vertical menu.  
Active link gets a darker background highlight.

### Footer (3-column grid)
| Column 1 | Column 2 | Column 3 |
|---|---|---|
| CRO description | Quick Links (About, Our Work, Team) | Partners (IIIT Lucknow, UP Relief Commissioner's Office) |

Bottom bar: `© 2025 Climate Resilience Observatory — IIIT Lucknow`

---

## 6. Page-by-Page Content

### 6.1 Home Page (`/`)

**Section 1 — Hero**
- Left 2/3: Large visual area with a globe icon placeholder and caption overlay:
  - Title: **"Advancing Global Sustainability"**
  - Body: *"The Climate Resilience Observatory is working to protect communities through innovative data analysis and international cooperation."*
- Right 1/3 panel:
  - Label: `CRO INSIGHTS`
  - Heading: **"Leading the way in Climate Action and Risk Assessment."**
  - Body: *"Our initiative leverages advanced technology to ensure that decision-makers have the insights needed to foster a resilient future for all populations."*
  - CTA Button: **"Learn More »"** → links to `/about`

**Section 2 — Key Initiatives (4-column card grid)**
| Card | Icon | Title | Description |
|---|---|---|---|
| 1 | Shield | Risk Monitoring | Real-time analysis of environmental variables to predict and mitigate climate-related hazards. |
| 2 | Globe | Global Reach | Collaborative frameworks connecting researchers and policymakers across international borders. |
| 3 | MessageSquare | Public Awareness | Communicating complex climate data into actionable insights for local communities. |
| 4 | Handshake | Strategic Partnerships | Bridging the gap between academia, government, and the United Nations for unified action. |

**Section 3 — Secondary Banner (dark)**
- Text: *"Building resilience for a sustainable future"*
- CTA Button: **"Join the Effort"** → links to `/involved`

---

### 6.2 About Page (`/about`)

**Section 1 — Hero**
- Title: **"About the Observatory"**
- Sub: *"Pioneering the intersection of artificial intelligence and environmental stewardship to safeguard our shared future."*

**Section 2 — Core Values (4-column grid)**
| Icon | Title | Description |
|---|---|---|
| Target | Our Mission | To advance global climate resilience through the integration of cutting-edge technology and international research excellence. |
| Eye | Our Vision | A world where every community is empowered with the data and insights necessary to thrive on a healthy and sustainable planet. |
| Globe | Global Cooperation | Fostering inclusive partnerships between academia, government, and international bodies to unify climate action efforts. |
| BookOpen | Knowledge Sharing | Breaking down complex environmental data into accessible and actionable knowledge for decision-makers worldwide. |

**Section 3 — Initiative Detail (2-column)**
- Left: Narrative text about the joint strategic initiative, combining academic research with governmental implementation.
- Right: Impact card with statistics:
  - **24+** Researchers working across international disciplines.
  - **100K+** Community members protected by early warning systems.
  - **5+** Active transboundary projects currently in operation.

**Section 4 — Motto Bar (blue background)**
- *"Data-driven resilience for a sustainable future"*

---

### 6.3 Projects Page (`/projects`)

**Header:** "Our Work" — *"Showcasing global efforts in building climate resilience through data-driven insights and international collaboration."*

**Projects List (animated with Framer Motion, scroll-triggered):**

| # | Icon | Title | Status | Description |
|---|---|---|---|---|
| 1 | 🔥 | Global Heatwave Analysis | **Ongoing** | Coordinated initiatives to monitor and predict extreme temperature events, providing critical data to support urban cooling strategies and public health interventions. |
| 2 | 🌊 | Integrated Flood Risk Systems | **Ongoing** | Developing standardized methodologies for flood hazard mapping and risk communication, fostering regional cooperation in disaster risk reduction. |
| 3 | 🌧️ | Precipitation Modeling | **Ongoing** | Advanced hydrological research supporting sustainable water management practices and agricultural resilience in moisture-stressed regions. |
| 4 | 💧 | Transboundary Watershed Management | **Ongoing** | Fostering international dialogue and technical exchange for the sustainable management of shared water resources and ecosystem services. |
| 5 | ❄️ | Coldwave Impact Studies | **Archived** | Comprehensive analysis of coldwave patterns and socioeconomic vulnerabilities, contributing to effective winter preparedness and social protection policies. |

Each card has a "View Project Details »" button (not yet linked to a detail page).

---

### 6.4 Team Page (`/team`)

**Header:** "Our Team" — *"Meet the dedicated researchers and analysts contributing to global climate resilience and data-driven disaster risk reduction."*

**Section Label:** "Core Contributors"

**Full Team Member List (21 members):**

| # | Name | Programme | Photo File |
|---|---|---|---|
| 1 | Sahil Rafaliya | M.Sc. Data Science | *(none)* |
| 2 | Srishti Garg | M.Sc. Data Science | *(none)* |
| 3 | Rajesh | M.Sc. Data Science | *(none)* |
| 4 | Sunil Kumar | M.Sc. AI & ML | `Sunil.png` |
| 5 | Sridip Basu | M.Sc. AI & ML | `sridip-basu.png` |
| 6 | Kamal Vasa | M.Sc. AI & ML | `Kamal.png` |
| 7 | Samir Thakur | M.Sc. AI & ML | `samir.png` |
| 8 | Eleti Nithin Pious | M.Sc. AI & ML | *(none)* |
| 9 | Laxmikanta Roy | M.Sc. AI & ML | `laxmikant.png` |
| 10 | Harsh Jain | M.Sc. AI & ML | `Harsh.png` |
| 11 | Arjun Mahesh | M.Sc. AI & ML | `Arjun.png` |
| 12 | Rishabh Bedi | M.Sc. Data Science | *(none)* |
| 13 | Rohit Kumar Meena | M.Sc. Data Science | `Rohit.png` |
| 14 | Urmila Saini | M.Sc. Data Science | `Urmilla.png` |
| 15 | Rupsa Roy | M.Sc. Data Science | `Rupsa.png` |
| 16 | Debayan Bandyopadhyay | M.Sc. Data Science | `Debayan.png` |
| 17 | Aishrica | M.Sc. Data Science | `Aishrica.png` |
| 18 | Gunjan | M.Sc. Data Science | `Gunjan.png` |
| 19 | Tarun Rai | M.Sc. Data Science | `Tarun.png` |
| 20 | Manas Singh | M.Sc. Data Science | `Manas.png` |
| 21 | Shiva Singh | M.Sc. Data Science | `Shiva.png` |

> **Note:** Team photos are stored in `public/team-photos/`. Not all team members listed in `Team.tsx` have a corresponding photo file yet. Photos currently exist for 16 out of 21 members.

**Footer Quote Section:**
> *"Individually we are one drop, together we are an ocean. Our multi-disciplinary approach ensures that every perspective is valued in the fight against climate change."*

---

## 7. Design System & Theme Tokens

The site uses a UN-inspired (United Nations) color palette defined in `tailwind.config.ts`:

| Token Name       | Purpose                                              |
|------------------|------------------------------------------------------|
| `un-blue`        | Primary brand color (UN blue) — buttons, accents, borders |
| `un-dark-gray`   | Navigation bar, footer, dark section backgrounds      |
| `un-light-gray`  | Light section backgrounds, card hover states         |
| `background`     | Page background (white/off-white)                    |

### Typography
- **Font**: System `font-sans` default (no custom Google Font loaded)
- Heavy use of `uppercase`, `tracking-wider` / `tracking-tighter`, `font-bold` for headings
- UN-style institutional editorial typography

### Animation
- `animate-fade-in` class on every page root `<div>` for entry transition
- Framer Motion used on Projects page for scroll-triggered `opacity + x` slide-in

### Component Style Notes
- Cards: `rounded-none` (sharp corners — no border radius)
- Buttons: `rounded-none`, `uppercase`, `tracking-wider` — institutional look
- Active nav links: darker background highlight
- Hover states: cards gain `border-un-blue` and subtle shadow

---

## 8. Assets Summary

### Logos (in `src/assets/` — bundled at build time)
| File | Usage |
|---|---|
| `cro-logo.jpg` | Site header logo |
| `iiitl-logo.png` | IIIT Lucknow logo |
| `govt-up-logo.png` | Government of UP logo |
| `relief-commissioner-logo.jpg` | UP Relief Commissioner's Office logo |

### Team Photos (in `public/team-photos/` — served statically)
16 PNG files named after team members (see Section 6.4 for mapping).

---

## 9. Pages NOT Yet Built

| Route       | Nav Label    | Status                        |
|-------------|--------------|-------------------------------|
| `/involved` | Get Involved | Link in nav + home banner CTA, **but no page exists** |
| Project detail pages | — | "View Project Details »" button on each project card, **but no detail pages exist** |

---

## 10. Backend

The `backend/` folder only contains a Python `venv/` directory. **No actual Python backend code exists yet** — it appears to be a placeholder for a future backend implementation.

---

## 11. Key Observations for Rebuilding

1. **The site is an institutional/government-style website** — clean, UN-styled, minimal color use, lots of whitespace.
2. **All data is hardcoded** in the `.tsx` files — no API, no CMS, no database. Content can be directly copied from the page files.
3. **Team photos exist but are not yet connected** to the `Team.tsx` component — the page currently renders a generic `User` icon for all members. The photos are ready in `public/team-photos/` to be wired up.
4. **The "Get Involved" page and project detail pages are missing** — these are placeholders for future work.
5. **The UI component library (shadcn/ui)** provides ready-made components. If rebuilding, you can use shadcn/ui or replicate the card/button/tooltip behavior manually.
6. **Framer Motion** is used only on the Projects page for entrance animations, everything else uses a simple CSS fade-in class.
