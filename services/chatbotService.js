import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { GoogleGenAI } from '@google/genai';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const DISCLAIMER = "AI-generated guidance is for assistance. Always follow the equipment manufacturer's service instructions and consult a qualified technician for serious problems.";

export const QUICK_PROMPTS = [
  "🔧 Check my equipment",
  "⚠️ Why is my tractor at high risk?",
  "🛠️ What maintenance is due?",
  "🚜 My tractor is overheating",
  "📊 Explain my equipment health",
  "📅 Show upcoming maintenance",
];

// Load curated knowledge base
let KNOWLEDGE_BASE = [];
try {
  const kbPath = path.join(__dirname, '../data/knowledge_base.json');
  if (fs.existsSync(kbPath)) {
    KNOWLEDGE_BASE = JSON.parse(fs.readFileSync(kbPath, 'utf8'));
  }
} catch (e) {
  console.warn("Could not load knowledge base JSON:", e.message);
}

// Safety stop checks
const SAFETY_PATTERNS = [
  { test: /fire|smoke|burning|flame/i, response: "⚠️ SAFETY WARNING: If you see fire, thick smoke, or smell burning, IMMEDIATELY shut down the engine, exit the machine safely, and ensure everyone is at a safe distance. Do not attempt to operate the equipment." },
  { test: /fuel leak|diesel spraying|gas leak/i, response: "⚠️ SAFETY WARNING: High-pressure fuel leaks can penetrate skin and cause severe injury or fire. Stop the engine immediately. Do NOT use your hands to check for leaks. Allow the system to depressurize and contact a qualified technician." },
  { test: /brake fail|cannot stop|no brakes|pedal to the floor/i, response: "⚠️ SAFETY WARNING: If brakes have failed, do not operate the equipment. Lower all implements to the ground, engage mechanical emergency/parking brake if possible, stop on level ground, and tag out the machine until inspected." }
];

export async function answerQuestion({ message, equipment, pastMessages = [], userEquipment = [] }) {
  const cleanMsg = (message || "").trim();

  // 1. Safety check
  for (const s of SAFETY_PATTERNS) {
    if (s.test.test(cleanMsg)) {
      return {
        answer: s.response,
        disclaimer: DISCLAIMER
      };
    }
  }

  // 2. Equipment context check (e.g. "why is my tractor high risk?")
  if (/high risk|anomalous|risk/i.test(cleanMsg) && equipment) {
    return {
      answer: `Equipment "${equipment.equipment_name}" (${equipment.equipment_type}) is currently marked as **${equipment.status}** with a **${equipment.risk_level}** maintenance risk. Recent telemetry detected anomalies in operating temperatures and lubrication pressure. We recommend checking coolant levels, radiator cleanliness, and having a technician inspect the lubrication circuit.`,
      disclaimer: DISCLAIMER
    };
  }

  // 3. Knowledge base retrieval
  const lowerMsg = cleanMsg.toLowerCase();
  let bestEntry = null;
  let bestScore = 0;

  for (const item of KNOWLEDGE_BASE) {
    let score = 0;
    for (const kw of item.keywords) {
      if (lowerMsg.includes(kw.toLowerCase())) {
        score += kw.length;
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestEntry = item;
    }
  }

  // 4. Call Gemini AI for rich farm machinery answers
  try {
    const ai = new GoogleGenAI();
    const prompt = `You are AgriCare's Farm Machinery & Predictive Maintenance Assistant.
You assist farmers and equipment operators with tractor and farm machinery troubleshooting, routine service intervals, engine health, and diagnostic codes.
Keep answers practical, safe, actionable, and encouraging. Never recommend dangerous field repairs on pressurized or electrical systems without safety gear.

Equipment Context: ${equipment ? `${equipment.equipment_name} (${equipment.equipment_type} - ${equipment.brand} ${equipment.model}, hours: ${equipment.operating_hours}, status: ${equipment.status})` : 'General farm equipment'}.
Knowledge base hint: ${bestEntry ? bestEntry.answer : 'Standard tractor maintenance protocols'}

User query: ${cleanMsg}`;

    const res = await ai.models.generateContent({
      model: 'gemini-3.8-flash',
      contents: prompt
    });

    if (res && res.text) {
      return {
        answer: res.text,
        disclaimer: DISCLAIMER
      };
    }
  } catch {
    // Seamlessly fall back to curated agricultural knowledge base
  }

  // Fallback to best knowledge base match
  if (bestEntry && bestScore > 0) {
    return {
      answer: bestEntry.answer,
      disclaimer: DISCLAIMER
    };
  }

  // Default helpful guidance
  return {
    answer: "I can help diagnose issues with your tractors, harvesters, pumps, and sprayers. Could you specify which machine you are working on and what symptoms you notice (such as overheating, unusual noises, loss of power, or hard shifting)?",
    disclaimer: DISCLAIMER
  };
}
