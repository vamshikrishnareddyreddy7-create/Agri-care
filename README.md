# AgriCare — AI-Based Farm Equipment Management and Predictive Maintenance

A modern web application that manages agricultural equipment, keeps digital maintenance records, ingests operational telematics data (manual entry or CSV), identifies abnormal equipment conditions with predictive condition monitoring, estimates maintenance risk, provides actionable maintenance recommendations, and answers farm machinery troubleshooting questions through an AI assistant.

---

## Quick Start

```bash
# Install dependencies
npm install

# Run the development server (runs on port 3000)
npm run dev
```

Open **http://localhost:3000** and sign in with the pre-seeded demo account:

| Field    | Value              |
|----------|--------------------|
| Email    | `farmer@demo.com`  |
| Password | `demo1234`         |

The application starts in **Demo Mode**: it seeds realistic sample farm equipment (Tümosan 81.110 tractor, John Deere 5055E, Claas Lexion 5300 harvester, KSB pump, Hardi sprayer, maintenance logs, operational telematics readings, and predictions).

---

## Features

- **Dashboard**: Live KPIs (Total Equipment, In Good Condition, Maintenance Due, High Risk), health overview table, condition breakdown, 6-month maintenance trends, risk distribution, operating hour usage, and recent activity logs.
- **Equipment Management**: Register, view, edit, search, and filter farm machinery with full maintenance history and sensor telemetry.
- **Maintenance Records**: Track service logs (Oil change, hydraulic repair, engine repair, transmission service, regular inspection), cost tracking, parts replaced, and next service date scheduling.
- **Operational Telematics**: Log engine speed (RPM), torque, load %, coolant temperature, oil temperature, oil pressure, fuel rate, vehicle speed, and battery voltage manually or via bulk CSV upload.
- **Predictive Maintenance**: Evaluates operational telemetry against engine envelopes to identify abnormal conditions, calculates failure probability %, and provides preventative recommendations.
- **AI Troubleshooting Assistant**: Interactive agricultural assistant with safety triage, knowledge base guidance, and Gemini AI integration.
- **Reports & Analytics**: Equipment reports, maintenance cost breakdowns, prediction logs, and risk reports with CSV export.
- **Notifications & Alerts**: Service reminders, high risk alerts, and delivery simulation.

---

## Tech Stack & Architecture

- **Runtime**: Node.js 22 (ES Modules)
- **Server Framework**: Express.js
- **Templating Engine**: Nunjucks (Jinja2-compatible template inheritance, filters, and blocks)
- **Data Layer**: In-memory database store seeded with realistic farm equipment data
- **Predictive Analytics**: Condition monitoring and anomaly detection engine
- **AI Integration**: Google GenAI SDK (`@google/genai`) with curated agricultural machinery knowledge base fallback
- **Styling**: AgriCare CSS Design System (responsive layout, green agricultural palette, light/dark tokens)
