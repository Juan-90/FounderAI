# Validation Experiments

## experiments
```json
[
  {
    "hypothesis": "SMEs in manufacturing and retail sectors are more likely to adopt an AI-driven carbon tracking tool than those in professional services.",
    "method": "Distribute a 10-question online survey via industry mailing lists and LinkedIn groups, targeting 100 SMEs across manufacturing, retail, hospitality, and professional services. Collect data on perceived need, budget, and technical readiness.",
    "metric": "Percentage of respondents indicating a high interest (≥4 on a 5-point scale) in adopting such a tool.",
    "go_threshold": "60%",
    "estimated_cost_days": 3
  },
  {
    "hypothesis": "SMEs consider carbon reduction a high priority pain point that directly impacts profitability.",
    "method": "Conduct 10 semi-structured phone interviews with owners/managers of SMEs, asking them to rate the severity of carbon-related challenges and the urgency to address them.",
    "metric": "Average priority rating on a 5-point Likert scale.",
    "go_threshold": "4",
    "estimated_cost_days": 5
  },
  {
    "hypothesis": "A minimal dashboard prototype with key analytics and recommendation features will be perceived as intuitive and actionable by SMEs.",
    "method": "Develop a clickable prototype using Figma or InVision, present it to 5 SMEs in a 30-minute usability session, and collect SUS (System Usability Scale) scores and qualitative feedback.",
    "metric": "SUS score (0-100).",
    "go_threshold": "70",
    "estimated_cost_days": 7
  },
  {
    "hypothesis": "SMEs are willing to pay a subscription fee of $200/month for a carbon reduction analytics platform.",
    "method": "Run an online pricing survey presenting three price points ($100, $200, $300/month) and ask respondents to indicate willingness to pay.",
    "metric": "Percentage of respondents willing to pay at each price point.",
    "go_threshold": "30% at $200",
    "estimated_cost_days": 4
  },
  {
    "hypothesis": "At least 80% of target SMEs can provide the operational data required for AI analysis through their existing ERP or accounting systems.",
    "method": "Attempt data ingestion from 5 SMEs, testing connectivity to common ERP systems (e.g., QuickBooks, Xero, SAP Business One) and mapping required fields.",
    "metric": "Successful data import rate (% of SMEs).",
    "go_threshold": "80%",
    "estimated_cost_days": 6
  },
  {
    "hypothesis": "The MVP of EcoTrack-IA can be delivered within a 6-month development cycle with a small core team.",
    "method": "Create a detailed project plan using Agile methodology, estimate story points for core features, and calculate total effort in person-days.",
    "metric": "Estimated total development effort (person-days).",
    "go_threshold": "≤6 months (≈480 person-days)",
    "estimated_cost_days": 2
  }
]
```
