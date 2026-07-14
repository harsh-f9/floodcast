import { useEffect, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ThermometerSun, RefreshCw, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import "@/styles/heatwave.css";

import { getApiUrl } from "@/lib/api";

const COLORS = {
  deepOcean: "#0a3d62",
  offWhite: "#eef7ff",
};

const API_URL = getApiUrl("/heatwave-risk-up");

interface DistrictPrediction {
  district: string;
  temperature: number;
  humidity: number;
  risk: "LOW" | "MODERATE" | "HIGH";
  probability: number;
}

/** Demo data: 75 UP district names for fallback when API fails */
const DEMO_DISTRICT_NAMES = [
  "Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha", "Auraiya", "Ayodhya", "Azamgarh", "Baghpat", "Bahraich",
  "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti", "Bhadohi", "Bijnor", "Budaun", "Bulandshahr",
  "Chandauli", "Chitrakoot", "Deoria", "Etah", "Etawah", "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddha Nagar", "Ghaziabad",
  "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur", "Hardoi", "Hathras", "Jalaun", "Jaunpur", "Jhansi",
  "Kannauj", "Kanpur Dehat", "Kanpur Nagar", "Kasganj", "Kaushambi", "Kushinagar", "Lakhimpur Kheri", "Lalitpur", "Lucknow", "Maharajganj",
  "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar", "Pilibhit", "Pratapgarh",
  "Prayagraj", "Raebareli", "Rampur", "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur", "Shamli", "Shravasti", "Siddharthnagar",
  "Sitapur", "Sonbhadra", "Sultanpur", "Unnao", "Varanasi",
];

/** Generate deterministic demo predictions for fallback (seeded by district name) */
function getDemoPredictions(): DistrictPrediction[] {
  return DEMO_DISTRICT_NAMES.map((district) => {
    const hash = district.split("").reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0);
    const temp = 34 + (Math.abs(hash) % 14);
    const humidity = 10 + (Math.abs(hash >> 2) % 61);
    const risk: "LOW" | "MODERATE" | "HIGH" = temp >= 44 ? "HIGH" : temp >= 40 ? "MODERATE" : "LOW";
    const probRange = risk === "HIGH" ? [0.75, 0.95] : risk === "MODERATE" ? [0.45, 0.74] : [0.1, 0.44];
    const probability = probRange[0] + ((Math.abs(hash >> 4) % 100) / 100) * (probRange[1] - probRange[0]);
    return { district, temperature: temp, humidity, risk, probability: Math.round(probability * 100) / 100 };
  });
}

interface HeatwaveResponse {
  districts: DistrictPrediction[];
}

function getRiskRowClass(risk: string): string {
  switch (risk) {
    case "LOW":
      return "heatwave-row-low";
    case "MODERATE":
      return "heatwave-row-moderate";
    case "HIGH":
      return "heatwave-row-high";
    default:
      return "";
  }
}

function getRiskBadgeClass(risk: string): string {
  switch (risk) {
    case "LOW":
      return "bg-green-500/90 text-white";
    case "MODERATE":
      return "bg-amber-500/90 text-white";
    case "HIGH":
      return "bg-red-500/90 text-white";
    default:
      return "bg-gray-400 text-white";
  }
}

export default function HeatwaveDashboard() {
  const [data, setData] = useState<HeatwaveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemoData, setIsDemoData] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<Date | null>(null);
  const navigate = useNavigate();

  const fetchPredictions = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsDemoData(false);
    try {
      const res = await fetch(API_URL);
      if (!res.ok) {
        let message = `API error: ${res.status}`;
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") message = body.detail;
          else if (body?.detail) message = JSON.stringify(body.detail);
        } catch {
          // response wasn't JSON
        }
        setError(message);
        setData({ districts: getDemoPredictions() });
        setIsDemoData(true);
        setGeneratedAt(new Date());
        return;
      }
      const json: HeatwaveResponse = await res.json();
      if (!json?.districts?.length) {
        setData({ districts: getDemoPredictions() });
        setIsDemoData(true);
        setError("API returned no districts");
      } else {
        setData(json);
        setError(null);
      }
      setGeneratedAt(new Date());
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load predictions";
      setError(message);
      setData({ districts: getDemoPredictions() });
      setIsDemoData(true);
      setGeneratedAt(new Date());
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchPredictions();
  }, [fetchPredictions]);

  const highCount = data?.districts?.filter((d) => d.risk === "HIGH").length ?? 0;
  const moderateCount = data?.districts?.filter((d) => d.risk === "MODERATE").length ?? 0;
  const lowCount = data?.districts?.filter((d) => d.risk === "LOW").length ?? 0;
  const total = data?.districts?.length ?? 0;

  return (
    <div className="min-h-screen bg-[#eef7ff] py-8 px-4 animate-fade-in font-sans">
      <div className="container mx-auto max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <Link
            to="/projects"
            className="inline-flex items-center text-[#0a3d62] hover:text-blue-800 font-semibold transition-colors"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Our Work
          </Link>
        </div>

        {/* Header */}
        <header className="mb-10">
          <div className="flex items-center gap-4 border-l-4 border-[#0a3d62] pl-6 py-2">
            <ThermometerSun className="w-12 h-12 text-orange-500" />
            <div>
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-[#0a3d62]">
                Heatwave Risk Dashboard
              </h1>
              <p className="text-gray-600 mt-1">Climate Resilience Observatory</p>
            </div>
          </div>
        </header>

        {/* Model Information Card */}
        <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 mb-8 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg text-gray-800 flex items-center gap-2">
              <ThermometerSun className="w-5 h-5 text-orange-500" />
              Model Information
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 text-sm text-gray-600">
            <div>
              <span className="font-semibold text-gray-700">Model Name:</span> Dummy Heatwave Predictor v1
            </div>
            <div>
              <span className="font-semibold text-gray-700">Generated:</span>{" "}
              {generatedAt
                ? generatedAt.toLocaleString()
                : loading
                  ? "—"
                  : "—"}
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
            <p className="font-medium">{error}</p>
            {isDemoData && (
              <p className="mt-2 text-amber-700">
                Showing demo data for all 75 districts. Start the backend with <code className="bg-amber-100 px-1 rounded">uvicorn main:app --reload</code> from the <code className="bg-amber-100 px-1 rounded">backend/</code> folder, then click <strong>Refresh Predictions</strong>.
              </p>
            )}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center gap-3 py-12 text-[#0a3d62]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="font-medium">Loading predictions…</span>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Summary Statistics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Total districts</p>
                  <p className="text-2xl font-bold text-[#0a3d62] mt-1">{total}</p>
                </CardContent>
              </Card>
              <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">High risk</p>
                  <p className="text-2xl font-bold text-red-600 mt-1">{highCount}</p>
                </CardContent>
              </Card>
              <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Moderate risk</p>
                  <p className="text-2xl font-bold text-amber-600 mt-1">{moderateCount}</p>
                </CardContent>
              </Card>
              <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Low risk</p>
                  <p className="text-2xl font-bold text-green-600 mt-1">{lowCount}</p>
                </CardContent>
              </Card>
            </div>

            {/* Refresh Button */}
            <div className="flex justify-end mb-4">
              <button
                onClick={fetchPredictions}
                disabled={loading}
                className="inline-flex items-center gap-2 bg-[#0a3d62] text-white px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-[#072a44] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                Refresh Predictions
              </button>
            </div>

            {/* District Prediction Table */}
            <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 overflow-hidden">
              <CardHeader className="border-b border-gray-100">
                <CardTitle className="text-lg text-gray-800">District predictions (Uttar Pradesh)</CardTitle>
                <p className="text-sm text-gray-500 mt-1">All 75 districts — risk based on simulated temperature</p>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto max-h-[60vh] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                      <tr>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700">District</th>
                        <th className="text-right py-3 px-4 font-semibold text-gray-700">Temperature (°C)</th>
                        <th className="text-right py-3 px-4 font-semibold text-gray-700">Humidity (%)</th>
                        <th className="text-center py-3 px-4 font-semibold text-gray-700">Risk level</th>
                        <th className="text-right py-3 px-4 font-semibold text-gray-700">Probability</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.districts.map((row) => (
                        <tr
                          key={row.district}
                          className={`border-b border-gray-100 ${getRiskRowClass(row.risk)}`}
                        >
                          <td className="py-3 px-4 font-medium text-gray-900">{row.district}</td>
                          <td className="py-3 px-4 text-right text-gray-700">{row.temperature}</td>
                          <td className="py-3 px-4 text-right text-gray-700">{row.humidity}</td>
                          <td className="py-3 px-4 text-center">
                            <span
                              className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${getRiskBadgeClass(row.risk)}`}
                            >
                              {row.risk}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right font-medium text-gray-800">
                            {(row.probability * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
