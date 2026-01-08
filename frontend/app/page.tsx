"use client";

import { useState } from "react";
import { Loader2, Trophy, ClipboardList, AlertCircle } from "lucide-react";

// Hardcoded NBA Team List
const NBA_TEAMS = [
  { id: 1610612737, name: "Atlanta Hawks" },
  { id: 1610612738, name: "Boston Celtics" },
  { id: 1610612739, name: "Cleveland Cavaliers" },
  { id: 1610612740, name: "New Orleans Pelicans" },
  { id: 1610612741, name: "Chicago Bulls" },
  { id: 1610612742, name: "Dallas Mavericks" },
  { id: 1610612743, name: "Denver Nuggets" },
  { id: 1610612744, name: "Golden State Warriors" },
  { id: 1610612745, name: "Houston Rockets" },
  { id: 1610612746, name: "LA Clippers" },
  { id: 1610612747, name: "Los Angeles Lakers" },
  { id: 1610612748, name: "Miami Heat" },
  { id: 1610612749, name: "Milwaukee Bucks" },
  { id: 1610612750, name: "Minnesota Timberwolves" },
  { id: 1610612751, name: "Brooklyn Nets" },
  { id: 1610612752, name: "New York Knicks" },
  { id: 1610612753, name: "Orlando Magic" },
  { id: 1610612754, name: "Indiana Pacers" },
  { id: 1610612755, name: "Philadelphia 76ers" },
  { id: 1610612756, name: "Phoenix Suns" },
  { id: 1610612757, name: "Portland Trail Blazers" },
  { id: 1610612758, name: "Sacramento Kings" },
  { id: 1610612759, name: "San Antonio Spurs" },
  { id: 1610612760, name: "Oklahoma City Thunder" },
  { id: 1610612761, name: "Toronto Raptors" },
  { id: 1610612762, name: "Utah Jazz" },
  { id: 1610612763, name: "Memphis Grizzlies" },
  { id: 1610612764, name: "Washington Wizards" },
  { id: 1610612765, name: "Detroit Pistons" },
  { id: 1610612766, name: "Charlotte Hornets" }
].sort((a, b) => a.name.localeCompare(b.name));

// Unique the list just in case of overlaps in my hardcoding
const UNIQUE_TEAMS = Array.from(new Map(NBA_TEAMS.map(item => [item.id, item])).values());

interface Tip {
  theme: string;
  text: string;
  score: number;
  evidence: string;
}

interface GameplanResponse {
  team_a: { win_prob: number; tips: Tip[] };
  team_b: { win_prob: number; tips: Tip[] };
}

export default function Home() {
  const [teamA, setTeamA] = useState<string>("");
  const [teamB, setTeamB] = useState<string>("");
  const [date, setDate] = useState<string>("2024-01-15");
  const [season, setSeason] = useState<string>("2023-24");
  const [window, setWindow] = useState<number>(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GameplanResponse | null>(null);

  const handleGenerate = async () => {
    if (!teamA || !teamB) {
      setError("Please select both teams.");
      return;
    }
    if (teamA === teamB) {
      setError("Teams must be different.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/gameplan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_a_id: parseInt(teamA),
          team_b_id: parseInt(teamB),
          season,
          as_of_date: date,
          window
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to generate gameplan");
      }

      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-extrabold text-gray-900 flex items-center justify-center gap-3">
            <Trophy className="text-orange-500 w-10 h-10" />
            NBA Gameplan Simulator
          </h1>
          <p className="mt-3 text-lg text-gray-600">
            Data-driven scouting reports and win probabilities
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white shadow-xl rounded-2xl p-8 mb-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Team A (Home)</label>
              <select
                className="w-full border-gray-300 rounded-lg shadow-sm focus:ring-orange-500 focus:border-orange-500 p-2.5 bg-gray-50 border"
                value={teamA}
                onChange={(e) => setTeamA(e.target.value)}
              >
                <option value="">Select Team</option>
                {UNIQUE_TEAMS.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <div className="lg:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Team B (Away)</label>
              <select
                className="w-full border-gray-300 rounded-lg shadow-sm focus:ring-orange-500 focus:border-orange-500 p-2.5 bg-gray-50 border"
                value={teamB}
                onChange={(e) => setTeamB(e.target.value)}
              >
                <option value="">Select Team</option>
                {UNIQUE_TEAMS.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">As of Date</label>
              <input
                type="date"
                className="w-full border-gray-300 rounded-lg shadow-sm focus:ring-orange-500 focus:border-orange-500 p-2 bg-gray-50 border"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Season</label>
              <select
                className="w-full border-gray-300 rounded-lg shadow-sm focus:ring-orange-500 focus:border-orange-500 p-2.5 bg-gray-50 border"
                value={season}
                onChange={(e) => setSeason(e.target.value)}
              >
                <option value="2023-24">2023-24</option>
                <option value="2022-23">2022-23</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Window (N)</label>
              <input
                type="number"
                min="1"
                max="82"
                className="w-full border-gray-300 rounded-lg shadow-sm focus:ring-orange-500 focus:border-orange-500 p-2 bg-gray-50 border"
                value={window}
                onChange={(e) => setWindow(parseInt(e.target.value))}
              />
            </div>
          </div>

          {error && (
            <div className="mt-6 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 flex items-center gap-3">
              <AlertCircle className="w-5 h-5" />
              {error}
            </div>
          )}

          <div className="mt-8">
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full bg-orange-600 text-white font-bold py-4 px-6 rounded-xl hover:bg-orange-700 transition duration-200 flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" />
                  Analyzing Matchup...
                </>
              ) : (
                "Generate Gameplan"
              )}
            </button>
          </div>
        </div>

        {/* Results */}
        {result && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Win Probabilities */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-2xl p-8 text-white shadow-lg text-center">
                <h3 className="text-xl font-semibold opacity-90 mb-2">
                  {UNIQUE_TEAMS.find(t => t.id === parseInt(teamA))?.name}
                </h3>
                <div className="text-6xl font-black">{(result.team_a.win_prob * 100).toFixed(1)}%</div>
                <div className="mt-2 font-medium opacity-80 uppercase tracking-wider text-sm">Win Probability</div>
              </div>

              <div className="bg-gradient-to-br from-red-600 to-red-800 rounded-2xl p-8 text-white shadow-lg text-center">
                <h3 className="text-xl font-semibold opacity-90 mb-2">
                  {UNIQUE_TEAMS.find(t => t.id === parseInt(teamB))?.name}
                </h3>
                <div className="text-6xl font-black">{(result.team_b.win_prob * 100).toFixed(1)}%</div>
                <div className="mt-2 font-medium opacity-80 uppercase tracking-wider text-sm">Win Probability</div>
              </div>
            </div>

            {/* Tips Columns */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white rounded-2xl p-8 shadow-md border-t-8 border-blue-500">
                <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                  <ClipboardList className="text-blue-500" />
                  Scouting Report: {UNIQUE_TEAMS.find(t => t.id === parseInt(teamA))?.name || "Team A"}
                </h3>
                <ul className="space-y-4">
                  {result.team_a.tips.map((tip, i) => (
                    <li key={i} className="flex flex-col gap-1 p-4 bg-blue-50 rounded-xl text-gray-800 leading-relaxed">
                      <div className="flex gap-4">
                        <span className="font-bold text-blue-600">{i + 1}.</span>
                        <div>
                          <span className="text-xs font-bold uppercase tracking-wider text-blue-400 block mb-1">{tip.theme}</span>
                          <p className="font-medium">{tip.text}</p>
                          <p className="text-sm text-gray-500 mt-1 italic">{tip.evidence}</p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-white rounded-2xl p-8 shadow-md border-t-8 border-red-500">
                <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                  <ClipboardList className="text-red-500" />
                  Scouting Report: {UNIQUE_TEAMS.find(t => t.id === parseInt(teamB))?.name || "Team B"}
                </h3>
                <ul className="space-y-4">
                  {result.team_b.tips.map((tip, i) => (
                    <li key={i} className="flex flex-col gap-1 p-4 bg-red-50 rounded-xl text-gray-800 leading-relaxed">
                      <div className="flex gap-4">
                        <span className="font-bold text-red-600">{i + 1}.</span>
                        <div>
                          <span className="text-xs font-bold uppercase tracking-wider text-red-400 block mb-1">{tip.theme}</span>
                          <p className="font-medium">{tip.text}</p>
                          <p className="text-sm text-gray-500 mt-1 italic">{tip.evidence}</p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

