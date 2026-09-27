# datta.ai Architecture

                         ┌──────────────────────┐
                         │    User Question     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Deterministic Plan   │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴───────────┐
                         ▼          ▼            ▼
                    Web Search  Web Search  Web Search ...
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Source Credibility   │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Groq Structured      │
                         │ Evidence Verification│
                         └──────────┬───────────┘
                                    │
                         Evidence strong?
                           │              │
                          yes             no
                           │              │
                           ▼              ▼
                       Final Report   Targeted Search
                                          │
                                          ▼
                                     Re-verification
                                          │
                                          ▼
                                      Final Report
