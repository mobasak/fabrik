import { useState } from "react";

const DAYS = [
  {
    id: "mon",
    label: "Monday",
    tag: "HOTEL GYM",
    tagColor: "#e74c3c",
    title: "Upper Push + V-Taper",
    focus: "Chest, Shoulders, Triceps, Abs",
    warmup: [
      "Incline treadmill walk — 5 min",
      "Band pull-aparts — 2×15",
      "Push-ups — 10 reps",
    ],
    blocks: [
      {
        name: "Heavy Compounds",
        exercises: [
          { name: "Incline Bench Press (bar)", sets: "4×5-6", note: "Heavy. Controls eccentric. V-taper priority — upper chest." },
          { name: "Flat Bench Press Machine", sets: "3×8", note: "Controlled. Chest stretch at bottom." },
          { name: "Shoulder Press Machine", sets: "4×5-6", note: "Strict. No back arch. Width builder." },
          { name: "Chest Squeeze Machine", sets: "3×10-12", note: "Squeeze peak contraction 2 sec." },
        ],
      },
      {
        name: "V-Taper Accessories",
        exercises: [
          { name: "Dumbbell Lateral Raise", sets: "4×12-15", note: "Light, controlled. Shoulder width = V-taper." },
          { name: "Reverse Shoulder Machine", sets: "3×12", note: "Rear delt health + posture." },
          { name: "Cable Tricep Pushdown", sets: "3×10-12", note: "Full lockout, slow negative." },
        ],
      },
      {
        name: "Lower Abs",
        exercises: [
          { name: "Hanging Leg Raise (bar)", sets: "4×8-10", note: "Posterior pelvic tilt. Slow." },
          { name: "Hanging Knee Raise ISO Hold", sets: "3×20 sec", note: "Tucked pelvis, squeeze." },
        ],
      },
      {
        name: "VO₂ Finisher",
        exercises: [
          { name: "Treadmill HIIT", sets: "6-8 rounds", note: "30 sec hard / 90 sec easy." },
          { name: "Incline Walk Cooldown", sets: "10 min", note: "Moderate pace." },
        ],
      },
    ],
  },
  {
    id: "tue",
    label: "Tuesday",
    tag: "HOTEL GYM",
    tagColor: "#e74c3c",
    title: "Pull + Legs + V-Taper",
    focus: "Back, Biceps, Legs, Abs",
    warmup: [
      "Treadmill walk — 5 min",
      "Bodyweight squats — 10 reps",
    ],
    blocks: [
      {
        name: "Heavy Compounds",
        exercises: [
          { name: "Deadlift or Romanian Deadlift (bar)", sets: "4×5", note: "Heavy. Posterior chain king." },
          { name: "Lat Pulldown Machine", sets: "4×6-8", note: "Full stretch top, squeeze bottom. Width." },
          { name: "Leg Press", sets: "4×8-10", note: "3 sec negative, full depth." },
          { name: "Lateral Pull Machine (seated row)", sets: "3×8", note: "Controlled squeeze. Back thickness." },
        ],
      },
      {
        name: "V-Taper + Legs",
        exercises: [
          { name: "Bulgarian Split Squat (dumbbells)", sets: "3×8 each", note: "Leg stability + glutes." },
          { name: "Dumbbell Curl", sets: "3×8-10", note: "Controlled negative. Arm aesthetics." },
          { name: "Farmer's Carry (heavy dumbbells)", sets: "4×30-40 sec", note: "Grip, traps, posture." },
        ],
      },
      {
        name: "Lower Abs",
        exercises: [
          { name: "Ab Wheel Rollout (on mat)", sets: "3×8", note: "Full extension if possible." },
          { name: "Weighted Reverse Crunch (bench)", sets: "3×10-12", note: "Slow hip lift." },
        ],
      },
      {
        name: "Zone 2 Cardio",
        exercises: [
          { name: "Incline Treadmill Walk", sets: "20-30 min", note: "Steady moderate pace. Fat burn zone." },
        ],
      },
    ],
  },
  {
    id: "wed",
    label: "Wednesday",
    tag: "OFFICE",
    tagColor: "#7f8c8d",
    title: "Mobility + Stretches",
    focus: "Recovery, Posture, Flexibility",
    warmup: [],
    blocks: [
      {
        name: "Every 30-45 min at desk",
        exercises: [
          { name: "Couch Stretch", sets: "60 sec each side", note: "Hip flexor opener." },
          { name: "Prone Press-up", sets: "10 reps", note: "Lumbar extension." },
          { name: "Dead Bug", sets: "2×8 reps", note: "Core stability." },
          { name: "Bird Dog", sets: "2×6 reps", note: "Anti-rotation." },
          { name: "Wall Slides", sets: "15 reps", note: "Shoulder mobility + posture." },
        ],
      },
    ],
  },
  {
    id: "thu",
    label: "Thursday",
    tag: "OFFICE",
    tagColor: "#7f8c8d",
    title: "Mobility + Stretches",
    focus: "Recovery, Posture, Flexibility",
    warmup: [],
    blocks: [
      {
        name: "Every 30-45 min at desk",
        exercises: [
          { name: "Couch Stretch", sets: "60 sec each side", note: "Hip flexor opener." },
          { name: "Prone Press-up", sets: "10 reps", note: "Lumbar extension." },
          { name: "Dead Bug", sets: "2×8 reps", note: "Core stability." },
          { name: "Bird Dog", sets: "2×6 reps", note: "Anti-rotation." },
          { name: "Wall Slides", sets: "15 reps", note: "Shoulder mobility + posture." },
        ],
      },
    ],
  },
  {
    id: "fri",
    label: "Friday",
    tag: "HOME GYM",
    tagColor: "#27ae60",
    title: "Full Body Strength A",
    focus: "Push + Pull-up Progression + Core",
    warmup: [
      "Crosstep — 5 min light",
      "Elevated Push-ups (handles) — 10 reps",
    ],
    blocks: [
      {
        name: "Strength",
        exercises: [
          { name: "Dumbbell Bench Press (flat/incline)", sets: "4×6-8", note: "18kg. Slow eccentric 3 sec." },
          { name: "Pull-up Progression", sets: "5×max (aim 2-4)", note: "Full dead hang. Build toward 5+ strict. REST 2 min." },
          { name: "Dumbbell Chest Fly", sets: "3×10-12", note: "Deep stretch, slow." },
          { name: "One-arm Dumbbell Row", sets: "3×8 each", note: "Bench-supported. Squeeze at top." },
          { name: "Dumbbell Lateral Raise", sets: "4×12-15", note: "V-taper. Light, constant tension." },
          { name: "Elevated Push-ups (handles)", sets: "3×max", note: "Deep ROM. Chest emphasis." },
          { name: "Dumbbell Curl (alternating)", sets: "3×8-10", note: "Controlled negative." },
        ],
      },
      {
        name: "Lower Abs",
        exercises: [
          { name: "Ab Wheel Rollout", sets: "4×8", note: "From knees if needed. Full extension." },
          { name: "Hanging Knee Raise (pull-up bar)", sets: "3×10-12", note: "Pelvic tilt at top." },
          { name: "Vacuum Hold", sets: "3×30 sec", note: "Waist tightening." },
        ],
      },
      {
        name: "Cardio",
        exercises: [
          { name: "Crosstep Intervals", sets: "15 min", note: "30 sec fast / 90 sec slow." },
        ],
      },
    ],
  },
  {
    id: "sat",
    label: "Saturday",
    tag: "HOME GYM",
    tagColor: "#27ae60",
    title: "Full Body Strength B",
    focus: "Legs + Pull + Posterior Chain",
    warmup: [
      "Crosstep — 5 min light",
      "Bodyweight squats — 15 reps",
    ],
    blocks: [
      {
        name: "Strength",
        exercises: [
          { name: "Dumbbell Romanian Deadlift", sets: "4×8", note: "18kg each. Hamstring stretch, hinge." },
          { name: "Dumbbell Bulgarian Split Squat", sets: "4×8 each leg", note: "Rear foot on bench. Deep." },
          { name: "Pull-up Progression", sets: "5×max (aim 2-4)", note: "Different grip than Friday (chin-up or wide)." },
          { name: "Dumbbell Overhead Press", sets: "3×8", note: "Seated on bench. Strict." },
          { name: "Dumbbell Chest Fly", sets: "3×10-12", note: "Maintain chest volume." },
          { name: "Farmer's Carry (18kg each)", sets: "4×30-40 sec", note: "Tight posture. Trap + grip work." },
        ],
      },
      {
        name: "Lower Abs",
        exercises: [
          { name: "Bench Reverse Crunch", sets: "4×12", note: "Grip bench overhead. Slow hip lift." },
          { name: "Lying Leg Raise with Hip Lift", sets: "3×12", note: "Lift hips off floor at top." },
        ],
      },
      {
        name: "Zone 2 Cardio",
        exercises: [
          { name: "Crosstep Steady State", sets: "30-40 min", note: "Moderate pace. Zone 2. Fat burn." },
        ],
      },
    ],
  },
  {
    id: "sun",
    label: "Sunday",
    tag: "HOME",
    tagColor: "#2980b9",
    title: "Active Recovery + Core",
    focus: "Mobility, Light Cardio, Deep Core",
    warmup: [],
    blocks: [
      {
        name: "Light Cardio",
        exercises: [
          { name: "Crosstep Zone 2", sets: "40 min", note: "Steady, easy pace. Recovery cardio." },
        ],
      },
      {
        name: "Deep Core & Mobility",
        exercises: [
          { name: "Dead Bug", sets: "3×8 each side", note: "Slow, controlled." },
          { name: "Bird Dog", sets: "3×6 each side", note: "Anti-rotation focus." },
          { name: "Side Plank", sets: "2×30 sec each", note: "Oblique stability." },
          { name: "Vacuum Hold", sets: "3×30 sec", note: "Waist tightening." },
          { name: "Ab Wheel Rollout (light)", sets: "2×8", note: "Easy sets. Maintenance." },
          { name: "Couch Stretch", sets: "90 sec each side", note: "Deep hip flexor release." },
          { name: "Prone Press-up", sets: "10 reps", note: "Spinal extension." },
        ],
      },
    ],
  },
];

const NUTRITION = {
  target: "~2,200–2,400 kcal/day",
  meals: [
    {
      name: "Meal 1 — 3-4 PM",
      items: [
        "30g egg white powder",
        "400-500ml kefir or yoghurt drink",
        "5g creatine + 5g taurine",
        "Rock salt",
      ],
      note: "If fat loss stalls → reduce kefir volume.",
    },
    {
      name: "Main Meal — Evening",
      items: [
        "300g lamb (trim visible fat) + 3 whole eggs",
        "OR 300g lamb + 150-200g lean beef",
      ],
      note: "No added olive oil. No desserts for 8-10 weeks.",
    },
  ],
  adjustRule: "Weigh daily → track weekly average. Loss < 0.4 kg/wk → reduce lamb 50g. Strength drops → increase protein slightly. Target: 0.4-0.6 kg/week.",
};

const SUPP_MORNING = [
  "Piracetam 1600mg",
  "L-Tyrosine 500mg",
  "Niacin (Nicotinic Acid) 100mg",
  "Bacopa 500mg",
  "Bladderwrack",
  "Rosemary Extract 500mg",
  "Fisetin 8mg",
  "Ergothioneine 25mg",
  "Pine Bark 100mg",
  "Boron 4mg",
  "MMST (Silicon) 5mg",
];

const SUPP_AFTERNOON = [
  "Citrulline Malate 3-5g",
  "Creatine Monohydrate 2.5g",
  "Beta-Alanine 2.5g",
  "TMG + Methyl-B12 + Methylfolate",
  "Magnesium 200mg (malate/glycinate/taurate) — 1st dose",
  "Ca-AKG",
  "CoQ10",
  "ALA (Alpha Lipoic Acid)",
  "Rutin 450mg",
  "Cinnamon Extract",
  "Phosphatidylserine",
  "Horny Goat Weed",
  "Bilberry Powder",
  "Aronia Extract",
];

const SUPP_DINNER = [
  "Multivitamin (1 capsule)",
  "Fish Oil — EPA 435 / DHA 290mg",
  "Joint Formula (Glucosamine/Chondroitin/MSM/Boswellia/HA)",
  "L. reuteri + L. salivarius",
  "Lutein 40mg + Zeaxanthin 2mg",
  "Hyaluronic Acid",
  "Milk Thistle",
  "Green Tea Extract",
  "Vitamin K2 MK-7 100mcg",
  "Magnesium 200mg (malate/glycinate/taurate) — 2nd dose",
];

const SUPP_BEDTIME = [
  "Glycine 10g",
  "NAC 600mg",
  "Magnesium 200mg (malate/glycinate/taurate) — 3rd dose",
  "Taurine",
  "Tryptophan",
];

const SUPP_OTHER = [
  "Vitamin D3 — 300,000 IU monthly (winter)",
];

const MILESTONES = [
  { week: "Week 2", waist: "90-91 cm", weight: "~87 kg" },
  { week: "Week 4", waist: "88-89 cm", weight: "~86 kg" },
  { week: "Week 6", waist: "86-87 cm", weight: "~85 kg" },
  { week: "Week 8-10", waist: "82-85 cm", weight: "82-84 kg" },
];

const TABS = ["Schedule", "Nutrition", "Supplements", "Progress"];

export default function FitnessPlan() {
  const [activeTab, setActiveTab] = useState(0);
  const [selectedDay, setSelectedDay] = useState(null);
  const [expandedBlocks, setExpandedBlocks] = useState({});

  const toggleBlock = (blockIdx) => {
    setExpandedBlocks((prev) => ({ ...prev, [blockIdx]: !prev[blockIdx] }));
  };

  const openDay = (day) => {
    setSelectedDay(day);
    const initExpanded = {};
    day.blocks.forEach((_, i) => (initExpanded[i] = true));
    setExpandedBlocks(initExpanded);
  };

  return (
    <div style={{ fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace", background: "var(--bg, #0a0a0a)", color: "var(--text, #e0e0e0)", minHeight: "100vh", padding: "0" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
        :root {
          --bg: #0a0a0a;
          --surface: #141414;
          --surface2: #1a1a1a;
          --border: #2a2a2a;
          --text: #e0e0e0;
          --text2: #888;
          --accent: #ff4444;
          --green: #27ae60;
          --blue: #2980b9;
          --orange: #e67e22;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        .tab-bar { display: flex; border-bottom: 1px solid var(--border); background: var(--surface); position: sticky; top: 0; z-index: 10; }
        .tab-btn { flex: 1; padding: 14px 8px; text-align: center; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; border: none; background: none; color: var(--text2); cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; font-family: inherit; }
        .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
        .day-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 8px 16px; cursor: pointer; transition: all 0.15s; }
        .day-card:hover { border-color: #444; transform: translateY(-1px); }
        .day-tag { display: inline-block; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; padding: 3px 8px; border-radius: 3px; color: #fff; margin-bottom: 8px; }
        .block-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; cursor: pointer; border-bottom: 1px solid var(--border); }
        .block-header:hover { color: #fff; }
        .exercise-row { display: flex; flex-direction: column; padding: 10px 0; border-bottom: 1px solid #1e1e1e; }
        .exercise-row:last-child { border-bottom: none; }
        .back-btn { background: none; border: 1px solid var(--border); color: var(--text2); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-family: inherit; font-size: 12px; margin: 16px; transition: all 0.15s; }
        .back-btn:hover { border-color: var(--accent); color: var(--accent); }
        .milestone-row { display: flex; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border); }
        .milestone-bar { height: 4px; background: var(--accent); border-radius: 2px; transition: width 0.5s; }
        .nutrition-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 8px 16px; }
        .pill { display: inline-block; background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 6px 12px; margin: 4px; font-size: 11px; color: var(--text2); }
      `}</style>

      {/* Header */}
      <div style={{ padding: "24px 16px 16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: "#fff", letterSpacing: "-0.5px" }}>
          CUT PROTOCOL
        </div>
        <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 4, letterSpacing: "0.5px" }}>
          88→83 KG · 94→82 CM · 8-12 WEEKS · CARNIVORE
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        {TABS.map((t, i) => (
          <button key={t} className={`tab-btn ${activeTab === i ? "active" : ""}`} onClick={() => { setActiveTab(i); setSelectedDay(null); }}>
            {t}
          </button>
        ))}
      </div>

      {/* SCHEDULE TAB */}
      {activeTab === 0 && !selectedDay && (
        <div style={{ padding: "8px 0 24px" }}>
          <div style={{ padding: "12px 16px 4px", fontSize: 10, color: "var(--text2)", letterSpacing: "1.5px", textTransform: "uppercase" }}>
            Weekly Split — Tap a day for details
          </div>
          {DAYS.map((day) => (
            <div key={day.id} className="day-card" onClick={() => openDay(day)}>
              <span className="day-tag" style={{ background: day.tagColor }}>{day.tag}</span>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <div>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: "#fff" }}>
                    {day.label}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text)", marginTop: 2 }}>{day.title}</div>
                </div>
                <div style={{ fontSize: 11, color: "var(--text2)" }}>{day.focus}</div>
              </div>
              <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 8 }}>
                {day.blocks.reduce((sum, b) => sum + b.exercises.length, 0)} exercises · {day.blocks.length} blocks
              </div>
            </div>
          ))}

          {/* Weekly cardio summary */}
          <div style={{ margin: "16px", padding: "16px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}>
            <div style={{ fontSize: 10, color: "var(--text2)", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8 }}>
              Weekly Cardio Target: 150-180 min
            </div>
            <div style={{ fontSize: 12, color: "var(--text)" }}>
              Mon HIIT ~20 min · Tue Zone 2 ~25 min · Fri Intervals ~15 min · Sat Zone 2 ~35 min · Sun Zone 2 ~40 min ≈ <span style={{ color: "#27ae60", fontWeight: 600 }}>~135-155 min</span> + incline walks
            </div>
          </div>
        </div>
      )}

      {/* DAY DETAIL VIEW */}
      {activeTab === 0 && selectedDay && (
        <div style={{ padding: "0 0 24px" }}>
          <button className="back-btn" onClick={() => setSelectedDay(null)}>← Back</button>
          <div style={{ padding: "0 16px 16px" }}>
            <span className="day-tag" style={{ background: selectedDay.tagColor }}>{selectedDay.tag}</span>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 20, fontWeight: 700, color: "#fff" }}>
              {selectedDay.label} — {selectedDay.title}
            </div>
            <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 4 }}>{selectedDay.focus}</div>
          </div>

          {selectedDay.warmup.length > 0 && (
            <div style={{ margin: "0 16px 8px", padding: 12, background: "var(--surface2)", borderRadius: 6, border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 10, color: "var(--orange)", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 6 }}>Warm-up</div>
              {selectedDay.warmup.map((w, i) => (
                <div key={i} style={{ fontSize: 12, color: "var(--text2)", padding: "2px 0" }}>• {w}</div>
              ))}
            </div>
          )}

          {selectedDay.blocks.map((block, bi) => (
            <div key={bi} style={{ margin: "0 16px 4px" }}>
              <div className="block-header" onClick={() => toggleBlock(bi)}>
                <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.5px", textTransform: "uppercase" }}>
                  {block.name}
                </span>
                <span style={{ fontSize: 14, color: "var(--text2)" }}>
                  {expandedBlocks[bi] ? "−" : "+"} {block.exercises.length}
                </span>
              </div>
              {expandedBlocks[bi] && (
                <div style={{ paddingLeft: 8 }}>
                  {block.exercises.map((ex, ei) => (
                    <div key={ei} className="exercise-row">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <span style={{ fontSize: 13, color: "#fff", fontWeight: 500 }}>{ex.name}</span>
                        <span style={{ fontSize: 12, color: "var(--accent)", fontWeight: 600, whiteSpace: "nowrap", marginLeft: 8 }}>{ex.sets}</span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 3 }}>{ex.note}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* NUTRITION TAB */}
      {activeTab === 1 && (
        <div style={{ padding: "8px 0 24px" }}>
          <div style={{ padding: "12px 16px", fontSize: 10, color: "var(--text2)", letterSpacing: "1.5px", textTransform: "uppercase" }}>
            Carnivore Cut — {NUTRITION.target}
          </div>
          {NUTRITION.meals.map((meal, i) => (
            <div key={i} className="nutrition-card">
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 8, fontFamily: "'Space Grotesk', sans-serif" }}>
                {meal.name}
              </div>
              {meal.items.map((item, j) => (
                <div key={j} style={{ fontSize: 12, color: "var(--text)", padding: "3px 0" }}>• {item}</div>
              ))}
              <div style={{ fontSize: 11, color: "var(--orange)", marginTop: 8, fontStyle: "italic" }}>{meal.note}</div>
            </div>
          ))}
          <div style={{ margin: "8px 16px", padding: 16, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}>
            <div style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8 }}>
              Adjustment Rule
            </div>
            <div style={{ fontSize: 12, color: "var(--text)" }}>{NUTRITION.adjustRule}</div>
          </div>
        </div>
      )}

      {/* SUPPLEMENTS TAB */}
      {activeTab === 2 && (
        <div style={{ padding: "16px" }}>
          {[
            { label: "Morning — Cognitive + Longevity", items: SUPP_MORNING, color: "#e67e22" },
            { label: "Afternoon — Vascular + Energy", items: SUPP_AFTERNOON, color: "#2980b9" },
            { label: "After Dinner — Repair + Structural", items: SUPP_DINNER, color: "#27ae60" },
            { label: "Before Bed — Recovery + Sleep", items: SUPP_BEDTIME, color: "#9b59b6" },
            { label: "Periodic", items: SUPP_OTHER, color: "var(--text2)" },
          ].map((group, gi) => (
            <div key={gi} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 10, color: group.color, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8 }}>
                {group.label}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap" }}>
                {group.items.map((s, i) => <span key={i} className="pill">{s}</span>)}
              </div>
            </div>
          ))}
          <div style={{ marginTop: 8, padding: 12, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11, color: "var(--text2)" }}>
            ⚠ Arimidex dropped. Creatine: 2.5g afternoon daily. Magnesium 600mg split 3×200mg (noon/evening/bed). During cut: maintain full stack. Taurine taken separately + via Mg Taurate.
          </div>
        </div>
      )}

      {/* PROGRESS TAB */}
      {activeTab === 3 && (
        <div style={{ padding: "16px" }}>
          <div style={{ fontSize: 10, color: "var(--text2)", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 12 }}>
            Target Milestones
          </div>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
            {MILESTONES.map((m, i) => (
              <div key={i} className="milestone-row">
                <div style={{ width: 80, fontSize: 12, fontWeight: 600, color: "#fff" }}>{m.week}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: "var(--text)" }}>Waist: {m.waist}</span>
                    <span style={{ fontSize: 12, color: "var(--text2)" }}>{m.weight}</span>
                  </div>
                  <div style={{ background: "var(--border)", borderRadius: 2, height: 4 }}>
                    <div className="milestone-bar" style={{ width: `${25 * (i + 1)}%` }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
            <div style={{ fontSize: 10, color: "var(--green)", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 10 }}>
              Success Conditions
            </div>
            {["Waist under 85 cm", "Lower abs visible (flexed)", "Strength maintained within 5%", "Energy stable", "No joint pain"].map((c, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--text)", padding: "4px 0" }}>✓ {c}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
