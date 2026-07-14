import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, MapPin, Activity, ThermometerSun, Waves, CloudRain, Zap, Snowflake } from "lucide-react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

// Match slugs to a nice title and icon
const MODEL_DETAILS: Record<string, { title: string, icon: JSX.Element }> = {
  "heatwave-analysis": { title: "Heatwave Prediction", icon: <ThermometerSun className="w-8 h-8 text-orange-500" /> },
  "flood-risk": { title: "Flood Risk Prediction", icon: <Waves className="w-8 h-8 text-blue-500" /> },
  "precipitation-modeling": { title: "Rainfall Prediction", icon: <CloudRain className="w-8 h-8 text-indigo-500" /> },
  "watershed-management": { title: "Lightning Prediction", icon: <Zap className="w-8 h-8 text-yellow-500" /> },
  "coldwave-impact": { title: "Coldwave Prediction", icon: <Snowflake className="w-8 h-8 text-cyan-500" /> },
};

interface PredictionResult {
  district: string;
  latitude: number;
  longitude: number;
  probability: number;
  risk_level: string;
  meteo_data?: {
    current_wind_speed: number | null;
    max_temp: number | null;
    max_wind: number | null;
    rain_sum: number | null;
    precip_sum: number | null;
  };
}

const ProjectDetail = () => {
  const { slug } = useParams();
  const [districts, setDistricts] = useState<string[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState<string>("");
  const [isPredicting, setIsPredicting] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);

  const modelDef = slug ? MODEL_DETAILS[slug] : null;

  useEffect(() => {
    // Fetch UP districts from backend
    fetch(getApiUrl("/api/districts"))
      .then((res) => res.json())
      .then((data) => {
        setDistricts(data.districts || []);
      })
      .catch((err) => console.error("Failed to load districts", err));
  }, []);

  const handlePredict = async () => {
    if (!selectedDistrict || !slug) return;
    setIsPredicting(true);
    setResult(null);

    try {
      const formattedDistrict = selectedDistrict.trim().split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
      
      const resp = await fetch(getApiUrl("/api/predict"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ district: formattedDistrict, model_slug: slug })
      });

      if (!resp.ok) {
        alert(`District "${selectedDistrict}" not found. Please check your spelling.`);
        setIsPredicting(false);
        return;
      }

      const data = await resp.json();
      setResult(data);
    } catch (err) {
      console.error("Prediction failed:", err);
    } finally {
      setIsPredicting(false);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case "Low": return "bg-green-500";
      case "Medium": return "bg-yellow-500";
      case "High": return "bg-orange-500";
      case "Extreme": return "bg-red-600";
      default: return "bg-gray-400";
    }
  };

  const getRiskTextColor = (level: string) => {
    switch (level) {
      case "Low": return "text-green-600";
      case "Medium": return "text-yellow-600";
      case "High": return "text-orange-600";
      case "Extreme": return "text-red-700";
      default: return "text-gray-600";
    }
  };

  if (!modelDef) {
    return <div className="p-20 text-center font-bold text-2xl">Model not found.</div>;
  }

  return (
    <div className="min-h-screen bg-[#eef7ff] py-12 px-4 animate-fade-in font-sans">
      <div className="max-w-4xl mx-auto">
        
        {/* Header */}
        <Link to="/projects" className="inline-flex items-center text-[#0a3d62] hover:text-blue-800 font-semibold mb-8 transition-colors">
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back to Our Work
        </Link>
        
        <div className="flex items-center gap-4 mb-10 border-l-4 border-[#0a3d62] pl-6 py-2">
          {modelDef.icon}
          <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-[#0a3d62] uppercase">
            {modelDef.title}
          </h1>
        </div>

        {/* Control Panel */}
        <Card className="bg-white p-6 rounded-2xl shadow-xl shadow-blue-900/5 border-none mb-10 overflow-visible relative z-10">
          <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-gray-500" />
            Select District (Uttar Pradesh)
          </h2>
          
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <input 
              type="text"
              list="districts-list"
              placeholder="Type District Name (e.g. Lucknow)"
              className="w-full sm:w-64 p-3 border border-gray-200 rounded-lg bg-gray-50 text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#0a3d62] text-sm font-medium relative z-20 cursor-text pointer-events-auto"
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handlePredict();
              }}
            />
            <datalist id="districts-list">
              {districts.map(d => (
                <option key={d} value={d} />
              ))}
            </datalist>
            
            <button
              onClick={handlePredict}
              disabled={isPredicting || !selectedDistrict}
              className="flex items-center justify-center gap-2 w-full sm:w-auto bg-[#0a3d62] text-white px-6 py-2.5 rounded-lg font-bold text-sm hover:bg-[#072a44] disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {isPredicting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Predicting
                </>
              ) : (
                <>
                  <Activity className="w-4 h-4" />
                  Run Model
                </>
              )}
            </button>
          </div>
        </Card>

        {/* Results Panel */}
        {result && (
          <div className="animate-fade-in">
            <Card className="bg-white p-8 sm:p-10 rounded-2xl shadow-2xl shadow-blue-900/10 border border-gray-100 relative overflow-hidden">
              <div className="flex flex-col md:flex-row gap-10 items-center">
                
                {/* Result Info */}
                <div className="flex-1 space-y-6 text-center md:text-left">
                  <div>
                    <h3 className="text-gray-500 font-bold uppercase tracking-widest text-sm mb-1">Target District</h3>
                    <p className="text-3xl font-bold text-gray-900">{result.district}</p>
                    <p className="text-gray-400 text-sm mt-1">
                      Lat: {result.latitude.toFixed(4)}, Lng: {result.longitude.toFixed(4)}
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="text-gray-500 font-bold uppercase tracking-widest text-sm mb-2">Probability Score</h3>
                    <div className="flex items-end gap-2 justify-center md:justify-start">
                      <span className={`text-6xl font-black ${getRiskTextColor(result.risk_level)}`}>
                        {result.probability.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Vertical Divider */}
                <div className="hidden md:block w-px h-auto min-h-[200px] bg-gray-200" />
                
                {/* Risk Gauge & Meteo Data Table */}
                <div className="flex-1 flex flex-col items-center justify-between min-h-[200px] self-stretch pt-2">
                  <div className="flex flex-col items-center">
                    <h3 className="text-gray-500 font-bold uppercase tracking-widest text-sm mb-4">Risk Level</h3>
                    
                    <div className={`px-8 py-3 rounded-2xl ${getRiskColor(result.risk_level)} border-4 border-white shadow-lg mb-6`}>
                      <p className="text-3xl font-black text-white uppercase tracking-wider">{result.risk_level}</p>
                    </div>
                  </div>
                  
                  {/* Open-Meteo Params Table */}
                  {result.meteo_data && (
                    <div className="w-full mt-auto pt-4 border-t border-gray-100">
                      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3 text-center md:text-right">Live Weather Parameters</h4>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                        <div className="flex justify-between items-center text-gray-600 bg-gray-50 px-2 py-1 rounded">
                          <span className="font-medium mr-2">Max Temp</span>
                          <span className="font-bold">{result.meteo_data.max_temp !== null ? `${result.meteo_data.max_temp}°C` : 'N/A'}</span>
                        </div>
                        <div className="flex justify-between items-center text-gray-600 bg-gray-50 px-2 py-1 rounded">
                          <span className="font-medium mr-2">Rain Sum</span>
                          <span className="font-bold">{result.meteo_data.rain_sum !== null ? `${result.meteo_data.rain_sum}mm` : 'N/A'}</span>
                        </div>
                        <div className="flex justify-between items-center text-gray-600 bg-gray-50 px-2 py-1 rounded">
                          <span className="font-medium mr-2">Max Wind</span>
                          <span className="font-bold">{result.meteo_data.max_wind !== null ? `${result.meteo_data.max_wind}km/h` : 'N/A'}</span>
                        </div>
                        <div className="flex justify-between items-center text-gray-600 bg-gray-50 px-2 py-1 rounded">
                          <span className="font-medium mr-2">Precip Sum</span>
                          <span className="font-bold">{result.meteo_data.precip_sum !== null ? `${result.meteo_data.precip_sum}mm` : 'N/A'}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Decorative progress bar at bottom */}
              <div className="absolute bottom-0 left-0 w-full h-3 bg-gray-100">
                <div 
                  className={`h-full ${getRiskColor(result.risk_level)} transition-all duration-1000 ease-out`} 
                  style={{ width: `${result.probability}%` }} 
                />
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectDetail;
