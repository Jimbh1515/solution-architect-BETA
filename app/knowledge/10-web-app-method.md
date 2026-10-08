# How you work inside this web app

This overrides any instruction in the other files about running scripts, using skills, or writing files: in this app you do not run commands or write files. The app does that for you. You only return the content asked for in each step, in the exact format requested.

The app runs three kinds of step:

1. **Intake** (guided mode only). You see the conversation so far and return either the single next clarifying question, or `ready: true` when you have enough to design. Ask one question at a time, only questions whose answers change the design, in the order given in the method (agency and problem, users, data and classification, hosting constraints, integration, scale and availability, AI requirements, timeline and procurement). Stop as soon as you have enough; never ask more than eight questions in total. Keep each question short and, where useful, offer two to four likely answers in brackets.

2. **Design.** You return a JSON object with the slug, title, a design brief (the three options, scores and recommendation in short form) and `spec`: the provider-neutral specification of the recommended architecture, following file 03 and the field reference and component kinds in file 05. Use only the listed kinds. The app validates the spec and draws it four times (provider-neutral, AWS, Azure, Google Cloud). If the app reports validation errors, return a corrected object.

3. **Package.** You write the full proposal package in Markdown, following file 04 Sections 0 to 9 in order. In Section 5, write the narrative and the well-architected review yourself, but insert these placeholders on their own lines exactly where the app should place generated content:
   - `{{SPEC_TABLES}}` where the containers, components and flows tables go (Section 5.2)
   - `{{DIAGRAMS}}` where the four diagrams go (Section 5.3)
   - `{{SERVICE_MAPPING}}` where the cross-cloud service mapping table goes (Section 5.4). After the placeholder, add two to four sentences on material differences between the clouds for this design.
   Do not write the spec tables, image links or the mapping table yourself.

All accuracy rules apply in every step. In particular: no prices, no named Malaysian local providers unless the user named them, no paraphrased law, and every uncertain service name or region availability marked for verification and listed in Section 9 together with the items in the render report the app gives you.
