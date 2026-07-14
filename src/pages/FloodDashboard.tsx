import { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Waves, RefreshCw, Loader2, MapPin, Target, Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { format, subDays, addDays } from "date-fns";
import { MapContainer, TileLayer, Marker, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/styles/heatwave.css"; // Reuse styling variables
import returnPeriodsData from "../data/gauge_return_periods.json";
import enrichedGauges from "../data/gauge_locations_enriched.json";
import { getApiUrl } from "@/lib/api";
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as ChartTooltip, 
  ReferenceLine 
} from "recharts";

const createCustomIcon = (isSelected: boolean, isGray: boolean = false, isHighlighted: boolean = false) => {
  let fillClass = "bg-[#43a047]"; // Default green
  if (isGray) {
    fillClass = "bg-[#9ca3af] scale-75"; // Small gray
  } else if (isHighlighted) {
    fillClass = "bg-[#2563eb] scale-110 z-40 animate-pulse shadow-[0_0_8px_rgba(37,99,235,0.6)]"; // Medium blue pulse
  }
  if (isSelected) {
    fillClass = "bg-[#ea580c] scale-125 z-50 ring-2 ring-orange-500/30"; // Large orange selected
  }
  
  return L.divIcon({
    className: 'custom-leaflet-icon',
    html: `<div class="w-4 h-4 ${fillClass} rounded-full border-[2.5px] border-white shadow-[0_2px_4px_rgba(0,0,0,0.4)] transition-all duration-200"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
};

const COLORS = {
  deepOcean: "#0a3d62",
  offWhite: "#eef7ff",
};

interface Station {
  station_id: number;
  station_name: string;
  latitude: number;
  longitude: number;
}

interface PredictionInfo {
  date: string;
  raw_streamflow: number;
}

interface StationDetail extends Station {
  UP_AREA: number;
  DIST_SINK: number;
  rp_2: number;
  rp_5: number;
  rp_15: number;
  rp_20: number;
  recent_predictions: PredictionInfo[];
}

function getRiskStatus(flow: number, station: StationDetail | null) {
  if (!station || !station.rp_2) return { label: "UNKNOWN", lightClass: "bg-gray-100 text-gray-800", darkClass: "bg-gray-500/20 text-gray-300" };
  if (flow < station.rp_2) return { label: "NORMAL", lightClass: "bg-emerald-100 text-emerald-800", darkClass: "bg-emerald-500/20 text-emerald-300" };
  if (flow < station.rp_5) return { label: "WATCH", lightClass: "bg-blue-100 text-blue-800", darkClass: "bg-blue-500/20 text-blue-300" };
  if (flow < station.rp_15) return { label: "WARNING", lightClass: "bg-amber-100 text-amber-800", darkClass: "bg-amber-500/20 text-amber-300" };
  if (flow < station.rp_20) return { label: "DANGER", lightClass: "bg-orange-100 text-orange-800", darkClass: "bg-orange-500/20 text-orange-300" };
  return { label: "EXTREME", lightClass: "bg-rose-100 text-rose-800", darkClass: "bg-rose-500/20 text-rose-300" };
}

export default function FloodDashboard() {
  const [stations, setStations] = useState<Station[]>([]);
  
  // Create a lookup map for enriched gauge details
  const gaugeLookup = useMemo(() => {
    const map: Record<string, any> = {};
    enrichedGauges.forEach((g) => {
      map[g.gauge_id] = g;
    });
    return map;
  }, []);
  const [stationsLoading, setStationsLoading] = useState(true);
  const [selectedDistrict, setSelectedDistrict] = useState<string>("");
  const [districtSearch, setDistrictSearch] = useState<string>("");
  
  // Extract all unique districts alphabetically
  const uniqueDistricts = useMemo(() => {
    const set = new Set<string>();
    enrichedGauges.forEach(g => {
      if (g.district) set.add(g.district);
    });
    return Array.from(set).sort();
  }, []);
  
  // Filter stations belonging to the selected district
  const districtGauges = useMemo(() => {
    if (!selectedDistrict) return [];
    if (selectedDistrict === "State-wide (All Districts)") return stations;
    return stations.filter(s => gaugeLookup[s.station_name]?.district === selectedDistrict);
  }, [selectedDistrict, stations, gaugeLookup]);
  
  const [selectedStationId, setSelectedStationId] = useState<number | null>(null);
  const [stationDetail, setStationDetail] = useState<StationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  
  const [targetDate, setTargetDate] = useState<string>(
    format(new Date(), "yyyy-MM-dd")
  );
  
  const [predicting, setPredicting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugFeatures, setDebugFeatures] = useState<Record<string, number> | null>(null);
  const [predResult, setPredResult] = useState<{
    pred_raw_streamflow: number;
    pred_delta_raw: number;
    anchor_streamflow: number;
    rainfall_mm_fetched: number;
    date: string;
  } | null>(null);

  const [trajectory, setTrajectory] = useState<{
    date: string;
    pred_raw_streamflow: number;
    pred_delta_raw: number;
    anchor_streamflow: number;
    rainfall_mm_fetched: number;
  }[] | null>(null);
  const [rainWindow, setRainWindow] = useState<{ date: string; rainfall_mm: number }[] | null>(null);

  const [masterPredictData, setMasterPredictData] = useState<Record<number, any> | null>(null);
  const [masterPredictLoading, setMasterPredictLoading] = useState(false);
  const [masterPredictProgress, setMasterPredictProgress] = useState(0);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState<string | null>(null);

  // Clear master predictions on district change
  useEffect(() => {
    setMasterPredictData(null);
    setReportModalOpen(false);
    setFilterSeverity(null);
  }, [selectedDistrict]);

  const getPeakSeverity = useCallback((stationId: number, data: any) => {
    const station = stations.find(s => s.station_id === stationId);
    if (!station) return { label: "UNKNOWN", color: "bg-gray-100 text-gray-800 border-gray-200", level: 0, peakFlow: 0, peakDate: "" };
    
    const thresholds = (returnPeriodsData as Record<string, any>)[station.station_name] || {
      watch: station.rp_2,
      warning: station.rp_5,
      danger: station.rp_15,
      extreme: station.rp_20
    };
    
    const traj = data.trajectory || [];
    let peakFlow = 0;
    let peakDate = "";
    
    traj.forEach((t: any) => {
      if (t.pred_raw_streamflow > peakFlow) {
        peakFlow = t.pred_raw_streamflow;
        peakDate = t.date;
      }
    });
    
    if (peakFlow === 0 && data.pred_raw_streamflow) {
      peakFlow = data.pred_raw_streamflow;
      peakDate = data.date;
    }
    
    let label = "NORMAL";
    let color = "bg-emerald-100 text-emerald-800 border-emerald-200";
    let level = 1;
    
    if (thresholds.watch && peakFlow >= thresholds.watch) {
      label = "WATCH";
      color = "bg-blue-100 text-blue-800 border-blue-200";
      level = 2;
    }
    if (thresholds.warning && peakFlow >= thresholds.warning) {
      label = "WARNING";
      color = "bg-amber-100 text-amber-800 border-amber-200";
      level = 3;
    }
    if (thresholds.danger && peakFlow >= thresholds.danger) {
      label = "DANGER";
      color = "bg-orange-100 text-orange-800 border-orange-200";
      level = 4;
    }
    if (thresholds.extreme && peakFlow >= thresholds.extreme) {
      label = "EXTREME";
      color = "bg-rose-100 text-rose-800 border-rose-200";
      level = 5;
    }
    
    return { label, color, level, peakFlow, peakDate, chartData: data.chartData };
  }, [stations]);

  const runMasterPredict = async () => {
    if (!selectedDistrict || districtGauges.length === 0) return;
    
    setMasterPredictLoading(true);
    setMasterPredictProgress(0);
    const results: Record<number, any> = {};
    
    try {
      const total = districtGauges.length;
      const baseDate = new Date("2026-07-14");
      
      for (let i = 0; i < total; i++) {
        const station = districtGauges[i];
        
        // 1. Fetch station details for past 6 days observations
        const resDetail = await fetch(getApiUrl(`/station/${station.station_id}`));
        if (!resDetail.ok) {
          throw new Error(`Failed to load details for station ${station.station_name}`);
        }
        const detailData = await resDetail.json();
        
        // 2. Fetch future 7-day trajectory prediction
        const response = await fetch(getApiUrl("/predict"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            station_id: station.station_id,
            date: "2026-07-21"
          })
        });
        
        if (!response.ok) {
          throw new Error(`Failed to predict for station ${station.station_name}`);
        }
        
        const data = await response.json();
        
        // 3. Pre-compute the 14-day chartData once and cache it in the object
        const chartList = [];
        for (let j = -6; j <= 7; j++) {
          const d = addDays(baseDate, j);
          const dateStr = format(d, "yyyy-MM-dd");
          
          const dbRow = detailData.recent_predictions?.find((r: any) => r.date === dateStr);
          const trajRow = data.trajectory?.find((r: any) => r.date === dateStr);
          
          let flowVal: number | null = null;
          if (dbRow) {
            flowVal = dbRow.raw_streamflow;
          } else if (trajRow) {
            flowVal = trajRow.pred_raw_streamflow;
          } else if (data.date === dateStr) {
            flowVal = data.pred_raw_streamflow;
          }
          
          chartList.push({
            date: dateStr,
            displayDate: format(d, "MMM dd"),
            streamflow: flowVal !== null ? Math.round(flowVal * 10) / 10 : null,
          });
        }
        
        results[station.station_id] = {
          ...data,
          recent_predictions: detailData.recent_predictions,
          chartData: chartList
        };
        
        setMasterPredictProgress(Math.round(((i + 1) / total) * 100));
      }
      
      setMasterPredictData(results);
      setReportModalOpen(true);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Master Predict failed.");
    } finally {
      setMasterPredictLoading(false);
    }
  };

  const runStateMasterPredict = async () => {
    const pwd = prompt("Enter Master Password to run State-wide Predictions:");
    if (pwd !== "cro") {
      alert("Access Denied: Invalid Password");
      return;
    }
    
    setSelectedDistrict("State-wide (All Districts)");
    setMasterPredictLoading(true);
    setMasterPredictProgress(0);
    const results: Record<number, any> = {};
    
    try {
      const total = stations.length;
      const baseDate = new Date("2026-07-14");
      const chunkSize = 8;
      
      for (let i = 0; i < total; i += chunkSize) {
        const chunk = stations.slice(i, i + chunkSize);
        
        await Promise.all(chunk.map(async (station) => {
          try {
            // 1. Fetch station details for past 6 days observations
            const resDetail = await fetch(getApiUrl(`/station/${station.station_id}`));
            if (!resDetail.ok) throw new Error("Fetch detail failed");
            const detailData = await resDetail.json();
            
            // 2. Fetch future 7-day trajectory prediction
            const response = await fetch(getApiUrl("/predict"), {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                station_id: station.station_id,
                date: "2026-07-21"
              })
            });
            
            if (!response.ok) throw new Error("Predict failed");
            const data = await response.json();
            
            // 3. Pre-compute chart data
            const chartList = [];
            for (let j = -6; j <= 7; j++) {
              const d = addDays(baseDate, j);
              const dateStr = format(d, "yyyy-MM-dd");
              
              const dbRow = detailData.recent_predictions?.find((r: any) => r.date === dateStr);
              const trajRow = data.trajectory?.find((r: any) => r.date === dateStr);
              
              let flowVal: number | null = null;
              if (dbRow) {
                flowVal = dbRow.raw_streamflow;
              } else if (trajRow) {
                flowVal = trajRow.pred_raw_streamflow;
              } else if (data.date === dateStr) {
                flowVal = data.pred_raw_streamflow;
              }
              
              chartList.push({
                date: dateStr,
                displayDate: format(d, "MMM dd"),
                streamflow: flowVal !== null ? Math.round(flowVal * 10) / 10 : null,
              });
            }
            
            results[station.station_id] = {
              ...data,
              recent_predictions: detailData.recent_predictions,
              chartData: chartList
            };
          } catch (e) {
            console.error(`Failed to predict for state gauge ID ${station.station_id}:`, e);
          }
        }));
        
        const currentProgress = Math.min(100, Math.round(((i + chunk.length) / total) * 100));
        setMasterPredictProgress(currentProgress);
      }
      
      setMasterPredictData(results);
      setReportModalOpen(true);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "State-wide Master Predict failed.");
    } finally {
      setMasterPredictLoading(false);
    }
  };

  // Generate 14-day chart data around the system baseline date (July 14, 2026)
  const chartData = useMemo(() => {
    if (!stationDetail) return [];
    
    // If we have pre-computed chartData in Master Predict, reuse it directly!
    const cached = masterPredictData?.[stationDetail.station_id]?.chartData;
    if (cached) return cached;
    
    // Anchor strictly to the system today baseline: July 14, 2026
    const baseDate = new Date("2026-07-14");

    const list = [];
    for (let i = -6; i <= 7; i++) {
      const d = addDays(baseDate, i);
      const dateStr = format(d, "yyyy-MM-dd");
      
      // 1. Look up in stationDetail.recent_predictions (stored predictions / historical observations)
      const dbRow = stationDetail.recent_predictions?.find(r => r.date === dateStr);
      
      // 2. Look up in trajectory (in-memory future forecast simulations if run)
      const trajRow = trajectory?.find(r => r.date === dateStr);
      
      // 3. Or check if we have the current prediction result
      let flowVal: number | null = null;
      if (dbRow) {
        flowVal = dbRow.raw_streamflow;
      } else if (trajRow) {
        flowVal = trajRow.pred_raw_streamflow;
      } else if (predResult && predResult.date === dateStr) {
        flowVal = predResult.pred_raw_streamflow;
      }
      
      list.push({
        date: dateStr,
        displayDate: format(d, "MMM dd"),
        streamflow: flowVal !== null ? Math.round(flowVal * 10) / 10 : null,
      });
    }
    return list;
  }, [stationDetail, trajectory, predResult, masterPredictData]);

  // 1. Fetch available stations on mount
  useEffect(() => {
    async function fetchStations() {
      try {
        setStationsLoading(true);
        const res = await fetch(getApiUrl("/stations"));
        if (!res.ok) throw new Error("Failed to load stations");
        const data = await res.json();
        setStations(data.stations || []);
      } catch (e) {
        setError("Could not load flood stations. Ensure backend is running.");
      } finally {
        setStationsLoading(false);
      }
    }
    fetchStations();
  }, []);

  // 2. Fetch specific station details when selected
  const fetchStationDetail = useCallback(async (id: number) => {
    try {
      setDetailLoading(true);
      setError(null);
      const res = await fetch(getApiUrl(`/station/${id}`));
      if (!res.ok) throw new Error(`Failed to load station ${id}`);
      const data = await res.json();
      setStationDetail(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedStationId !== null) {
      // Check if we have cached Master Predict data for this station
      const cached = masterPredictData?.[selectedStationId];
      if (cached) {
        setDebugFeatures(cached.debug_features || null);
        setRainWindow(cached.rain_window || null);
        if (cached.trajectory) {
          setTrajectory(cached.trajectory);
          setPredResult(null);
        } else {
          setTrajectory(null);
          setPredResult({
            pred_raw_streamflow: cached.pred_raw_streamflow,
            pred_delta_raw: cached.pred_delta_raw,
            anchor_streamflow: cached.anchor_streamflow,
            rainfall_mm_fetched: cached.rainfall_mm_fetched,
            date: cached.date,
          });
        }
      } else {
        setDebugFeatures(null);
        setPredResult(null);
        setTrajectory(null);
        setRainWindow(null);
      }
      fetchStationDetail(selectedStationId);
    }
  }, [selectedStationId, fetchStationDetail, masterPredictData]);

  // 3. Run prediction for selected station
  const runPrediction = async () => {
    if (selectedStationId === null) return;
    
    try {
      setPredicting(true);
      setError(null);
      const res = await fetch(getApiUrl("/predict"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          station_id: selectedStationId,
          date: targetDate,
        }),
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Prediction failed");
      }
      
      // Save debug features 
      setDebugFeatures(data.debug_features || null);
      setRainWindow(data.rain_window || null);
      
      if (data.trajectory) {
        setTrajectory(data.trajectory);
        setPredResult(null);
      } else {
        setTrajectory(null);
        setPredResult({
          pred_raw_streamflow: data.pred_raw_streamflow,
          pred_delta_raw: data.pred_delta_raw,
          anchor_streamflow: data.anchor_streamflow,
          rainfall_mm_fetched: data.rainfall_mm_fetched,
          date: data.date,
        });
      }
      
      // Refresh station detail to show new prediction in table
      await fetchStationDetail(selectedStationId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPredicting(false);
    }
  };

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
        <header className="mb-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4 relative">
          <div className="flex items-center gap-4 border-l-4 border-[#0a3d62] pl-6 py-2">
            <Waves className="w-12 h-12 text-[#0a3d62]" />
            <div>
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-[#0a3d62]">
                Flood Risk Dashboard
              </h1>
              <p className="text-gray-600 mt-1">Real-time Streamflow Prediction Model</p>
            </div>
          </div>
          
          {/* Top-Center State-wide Button */}
          <div className="flex items-center justify-center md:absolute md:left-1/2 md:-translate-x-1/2 md:top-1/2 md:-translate-y-1/2 mt-2 md:mt-0">
            <button
              onClick={runStateMasterPredict}
              disabled={masterPredictLoading}
              className="inline-flex items-center gap-2 bg-[#0a3d62] hover:bg-[#072a44] text-white px-5 py-2.5 rounded-xl font-bold text-xs shadow-md hover:shadow-blue-900/20 transition-all transform hover:-translate-y-0.5 disabled:opacity-50"
            >
              {masterPredictLoading && selectedDistrict === "State-wide (All Districts)" ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Running State: {masterPredictProgress}%
                </>
              ) : (
                <>
                  <Target className="w-3.5 h-3.5" />
                  State-wide Master Predict
                </>
              )}
            </button>
          </div>
          
          {/* Top-Right Report Button */}
          {masterPredictData && (
            <button
              onClick={() => setReportModalOpen(true)}
              className="inline-flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md hover:bg-indigo-700 hover:shadow-indigo-500/25 transition-all transform hover:-translate-y-0.5 self-start md:self-center font-bold"
            >
              <Activity className="w-4 h-4 animate-pulse" />
              View District Report
            </button>
          )}
        </header>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            <p className="font-medium">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* LEFT COLUMN: Controls */}
          <div className="lg:col-span-1 flex flex-col gap-6">
            
            <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100">
              <CardHeader className="border-b border-gray-100 pb-4">
                <CardTitle className="text-lg text-gray-800 flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-[#0a3d62]" />
                  1. Select Station
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 flex flex-col gap-4">
                {stationsLoading ? (
                  <div className="flex items-center text-sm text-gray-500">
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Loading stations...
                  </div>
                ) : (
                  <>
                    {/* District Search & Filter */}
                    <div className="flex flex-col gap-1.5">
                      <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Filter by District
                      </label>
                      <div className="relative">
                        <input
                          list="district-options"
                          type="text"
                          placeholder="Type to search district..."
                          value={districtSearch}
                          onChange={(e) => {
                            const val = e.target.value;
                            setDistrictSearch(val);
                            if (uniqueDistricts.includes(val)) {
                              setSelectedDistrict(val);
                              // Auto-select the first station in the selected district
                              const matchingGauges = stations.filter(s => gaugeLookup[s.station_name]?.district === val);
                              if (matchingGauges.length > 0) {
                                setSelectedStationId(matchingGauges[0].station_id);
                              }
                            } else if (val === "") {
                              setSelectedDistrict("");
                            }
                          }}
                          className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-[#0a3d62] outline-none transition-all"
                        />
                        <datalist id="district-options">
                          {uniqueDistricts.map(d => (
                            <option key={d} value={d} />
                          ))}
                        </datalist>
                        {selectedDistrict && (
                          <button
                            onClick={() => {
                              setSelectedDistrict("");
                              setDistrictSearch("");
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs font-bold text-gray-400 hover:text-gray-600 px-1 py-0.5"
                          >
                            Clear
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Master Predict District Button */}
                    {selectedDistrict && (
                      <div className="flex flex-col gap-2 p-3 bg-indigo-50/60 border border-indigo-100 rounded-xl">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-wider font-mono">
                            District Batch Run
                          </span>
                          <span className="text-xs font-semibold text-gray-500">
                            {districtGauges.length} stations
                          </span>
                        </div>
                        <button
                          onClick={runMasterPredict}
                          disabled={masterPredictLoading}
                          className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
                        >
                          {masterPredictLoading ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Running... {masterPredictProgress}%
                            </>
                          ) : (
                            <>
                              <Activity className="w-3.5 h-3.5" />
                              Master Predict (7 Days)
                            </>
                          )}
                        </button>
                        
                        {masterPredictLoading && (
                          <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                            <div 
                              className="bg-indigo-600 h-full transition-all duration-300"
                              style={{ width: `${masterPredictProgress}%` }}
                            ></div>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex flex-col gap-1.5">
                      <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Choose Gauge Station
                      </label>
                      <select 
                        className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-[#0a3d62] outline-none transition-all"
                        value={selectedStationId ?? ""}
                        onChange={(e) => setSelectedStationId(Number(e.target.value))}
                      >
                        <option value="" disabled>-- Choose a gauge station --</option>
                        {stations.map(s => {
                          const info = gaugeLookup[s.station_name];
                          const displayName = info
                            ? `${info.location_name}, ${info.sub_district}, ${info.district} (gauge id: ${s.station_id})`
                            : `${s.station_name} (gauge id: ${s.station_id})`;
                          
                          // If a district is selected, only show stations in that district
                          if (selectedDistrict && info?.district !== selectedDistrict) {
                            return null;
                          }
                          
                          return (
                            <option key={s.station_id} value={s.station_id}>
                              {displayName}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                    
                    <div className="h-[550px] w-full rounded-lg overflow-hidden border border-gray-200 shadow-inner relative z-0">
                      <MapContainer 
                        center={[27.0, 80.5]} 
                        zoom={6} 
                        minZoom={6}
                        maxBounds={[
                          [23.0, 76.5], // Southwest coordinates of UP
                          [31.0, 85.0]  // Northeast coordinates of UP
                        ]}
                        maxBoundsViscosity={1.0}
                        scrollWheelZoom={true} 
                        style={{ height: "100%", width: "100%" }}
                      >
                        <TileLayer
                          url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
                          attribution="&copy; Google Maps"
                        />
                        {stations.map((s, index) => {
                          if (!s.latitude || !s.longitude) return null;
                          const isSelected = selectedStationId === s.station_id;
                          
                          let isHighlighted = false;
                          let isGray = index % 4 === 0 && !isSelected;
                          
                          if (selectedDistrict) {
                            const isGaugeInDistrict = selectedDistrict === "State-wide (All Districts)"
                              ? true
                              : gaugeLookup[s.station_name]?.district === selectedDistrict;
                            isHighlighted = isGaugeInDistrict && !isSelected;
                            isGray = !isGaugeInDistrict && !isSelected;
                          }
                          
                          return (
                            <Marker
                              key={s.station_id}
                              position={[s.latitude, s.longitude]}
                              icon={createCustomIcon(isSelected, isGray, isHighlighted)}
                              eventHandlers={{
                                click: () => setSelectedStationId(s.station_id),
                                mouseover: (e) => e.target.openTooltip(),
                                mouseout: (e) => e.target.closeTooltip()
                              }}
                            >
                              <Tooltip direction="top" offset={[0, -12]} opacity={0.95}>
                                <div className="font-semibold text-gray-800">
                                  {gaugeLookup[s.station_name]?.location_name || s.station_name}
                                </div>
                                {gaugeLookup[s.station_name] && (
                                  <div className="text-xs text-gray-500 mt-0.5">
                                    {gaugeLookup[s.station_name].sub_district}, {gaugeLookup[s.station_name].district}
                                  </div>
                                )}
                                <div className="text-[10px] text-orange-600 font-bold font-mono mt-0.5">
                                  Gauge ID: {s.station_id}
                                </div>
                              </Tooltip>
                            </Marker>
                          );
                        })}
                      </MapContainer>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card className={`bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 transition-opacity ${selectedStationId === null ? 'opacity-50 pointer-events-none' : ''}`}>
              <CardHeader className="border-b border-gray-100 pb-4">
                <CardTitle className="text-lg text-gray-800 flex items-center gap-2">
                  <Target className="w-5 h-5 text-[#0a3d62]" />
                  2. Prediction Target
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">Target Date</label>
                  <input 
                    type="date" 
                    min={format(subDays(new Date(), 2), "yyyy-MM-dd")}
                    max={format(addDays(new Date(), 7), "yyyy-MM-dd")}
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-[#0a3d62] outline-none transition-all"
                  />
                </div>
                
                <button
                  onClick={runPrediction}
                  disabled={predicting || selectedStationId === null}
                  className="w-full flex justify-center items-center gap-2 bg-[#0a3d62] text-white px-5 py-3 rounded-lg font-semibold text-sm hover:bg-[#072a44] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {predicting ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Running Model...</>
                  ) : (
                    <><Activity className="w-4 h-4" /> Run Prediction</>
                  )}
                </button>
                <p className="text-xs text-gray-400 text-center">
                  Fetches 60d antecedent rainfall from Open-Meteo & invokes LSTM Model
                </p>
              </CardContent>
            </Card>

          </div>

          {/* RIGHT COLUMN: Results */}
          <div className="lg:col-span-2">
            {!stationDetail && !selectedStationId && (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center border-2 border-dashed border-gray-200 rounded-2xl bg-white/50">
                <Waves className="w-16 h-16 text-gray-300 mb-4" />
                <p className="text-gray-500 font-medium text-lg">Select a station to view details</p>
              </div>
            )}

            {detailLoading && !stationDetail && selectedStationId !== null && (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center rounded-2xl bg-white/50">
                <Loader2 className="w-8 h-8 text-[#0a3d62] animate-spin mb-4" />
                <p className="text-[#0a3d62] font-medium text-lg">Loading gauge data...</p>
              </div>
            )}

            {stationDetail && (
              <div className="flex flex-col gap-6 animate-fade-in">
                {/* District Gauge Carousel Navigation */}
                {selectedDistrict && districtGauges.length > 0 && (
                  <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-indigo-100 rounded-2xl shadow-md p-4 flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-600 font-mono">District Mode: {selectedDistrict}</span>
                      <span className="text-sm font-bold text-gray-800 mt-0.5">
                        Gauge {districtGauges.findIndex(g => g.station_id === selectedStationId) + 1} of {districtGauges.length}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          const idx = districtGauges.findIndex(g => g.station_id === selectedStationId);
                          if (idx !== -1) {
                            const prevIdx = (idx - 1 + districtGauges.length) % districtGauges.length;
                            setSelectedStationId(districtGauges[prevIdx].station_id);
                          }
                        }}
                        className="px-3.5 py-1.5 bg-white hover:bg-gray-50 border border-gray-200 rounded-lg text-xs font-bold text-[#0a3d62] flex items-center gap-1 shadow-sm transition-all"
                        title="Previous Gauge"
                      >
                        &larr; Prev
                      </button>
                      <button
                        onClick={() => {
                          const idx = districtGauges.findIndex(g => g.station_id === selectedStationId);
                          if (idx !== -1) {
                            const nextIdx = (idx + 1) % districtGauges.length;
                            setSelectedStationId(districtGauges[nextIdx].station_id);
                          }
                        }}
                        className="px-3.5 py-1.5 bg-white hover:bg-gray-50 border border-gray-200 rounded-lg text-xs font-bold text-[#0a3d62] flex items-center gap-1 shadow-sm transition-all"
                        title="Next Gauge"
                      >
                        Next &rarr;
                      </button>
                    </div>
                  </Card>
                )}

                {/* Gauge Title */}
                <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-xl shadow-blue-900/5 flex flex-col justify-center">
                  <h3 className="text-xl font-bold text-[#0a3d62] tracking-tight">
                    {gaugeLookup[stationDetail.station_name]?.location_name || stationDetail.station_name}
                  </h3>
                  <p className="text-xs text-gray-500 font-semibold mt-1">
                    {gaugeLookup[stationDetail.station_name]
                      ? `${gaugeLookup[stationDetail.station_name].sub_district}, ${gaugeLookup[stationDetail.station_name].district}, ${gaugeLookup[stationDetail.station_name].state}`
                      : "Gauge Location Details"}
                  </p>
                </div>

                {/* 2-Column Grid: Metadata & Thresholds vs. Trend Chart */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left Column: Metadata & Return Period Thresholds */}
                  <div className="flex flex-col gap-6">
                    {/* Meta Cards (2x2 grid for sub-column) */}
                    <div className="flex flex-col gap-2">
                      <p className="text-sm font-semibold text-gray-700">Station Specifications</p>
                      <div className="grid grid-cols-2 gap-3">
                        <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                          <CardContent className="p-4 flex flex-col justify-center">
                            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Latitude</p>
                            <p className="text-xl font-bold text-[#0a3d62] mt-1">{stationDetail.latitude.toFixed(4)}</p>
                          </CardContent>
                        </Card>
                        <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                          <CardContent className="p-4 flex flex-col justify-center">
                            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Longitude</p>
                            <p className="text-xl font-bold text-[#0a3d62] mt-1">{stationDetail.longitude.toFixed(4)}</p>
                          </CardContent>
                        </Card>
                        <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                          <CardContent className="p-4 flex flex-col justify-center">
                            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Upstream Area</p>
                            <p className="text-xl font-bold text-[#0a3d62] mt-1">{(stationDetail.UP_AREA / 1000).toFixed(1)}k</p>
                          </CardContent>
                        </Card>
                        <Card className="bg-white rounded-xl shadow-md border border-gray-100">
                          <CardContent className="p-4 flex flex-col justify-center">
                            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Dist to Sink</p>
                            <p className="text-xl font-bold text-[#0a3d62] mt-1">{stationDetail.DIST_SINK.toFixed(1)}</p>
                          </CardContent>
                        </Card>
                      </div>
                    </div>

                    {/* Return Period Thresholds (2x2 grid for sub-column) */}
                    {(() => {
                      const thresholds = (returnPeriodsData as Record<string, any>)[stationDetail.station_name] || {
                        watch: stationDetail.rp_2,
                        warning: stationDetail.rp_5,
                        danger: stationDetail.rp_15,
                        extreme: stationDetail.rp_20
                      };
                      return (
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold text-gray-700">Return Period Thresholds (m³/s)</p>
                            <span className="text-[10px] uppercase font-mono tracking-wider bg-gray-200 text-gray-700 px-2 py-0.5 rounded-full font-bold font-mono">Static DB</span>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <Card className="bg-blue-50/40 border border-blue-100 rounded-xl shadow-sm">
                              <CardContent className="p-3 flex flex-col justify-center">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700">Watch</span>
                                <p className="text-lg font-black text-blue-900 mt-1">
                                  {thresholds.watch ? thresholds.watch.toLocaleString(undefined, { maximumFractionDigits: 1 }) : 'N/A'}
                                </p>
                                <span className="text-[9px] text-blue-600/80 mt-0.5">rp_2 threshold</span>
                              </CardContent>
                            </Card>
                            <Card className="bg-amber-50/40 border border-amber-100 rounded-xl shadow-sm">
                              <CardContent className="p-3 flex flex-col justify-center">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700">Warning</span>
                                <p className="text-lg font-black text-amber-950 mt-1">
                                  {thresholds.warning ? thresholds.warning.toLocaleString(undefined, { maximumFractionDigits: 1 }) : 'N/A'}
                                </p>
                                <span className="text-[9px] text-amber-600/80 mt-0.5">rp_5 threshold</span>
                              </CardContent>
                            </Card>
                            <Card className="bg-orange-50/40 border border-orange-100 rounded-xl shadow-sm">
                              <CardContent className="p-3 flex flex-col justify-center">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-orange-700">Danger</span>
                                <p className="text-lg font-black text-orange-950 mt-1">
                                  {thresholds.danger ? thresholds.danger.toLocaleString(undefined, { maximumFractionDigits: 1 }) : 'N/A'}
                                </p>
                                <span className="text-[9px] text-orange-600/80 mt-0.5">rp_15 threshold</span>
                              </CardContent>
                            </Card>
                            <Card className="bg-rose-50/40 border border-rose-100 rounded-xl shadow-sm">
                              <CardContent className="p-3 flex flex-col justify-center">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700">Extreme</span>
                                <p className="text-lg font-black text-rose-950 mt-1">
                                  {thresholds.extreme ? thresholds.extreme.toLocaleString(undefined, { maximumFractionDigits: 1 }) : 'N/A'}
                                </p>
                                <span className="text-[9px] text-rose-600/80 mt-0.5">rp_20 threshold</span>
                              </CardContent>
                            </Card>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Right Column: 14-day Streamflow Trend Chart */}
                  <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 overflow-hidden flex flex-col h-full">
                    <CardHeader className="border-b border-gray-100 py-4 px-6 pb-2">
                      <CardTitle className="text-base text-gray-800">14-Day Streamflow Trend (m³/s)</CardTitle>
                      <p className="text-xs text-gray-400 mt-0.5">6d past forecast baseline &amp; 7d future simulation</p>
                    </CardHeader>
                    <CardContent className="p-4 flex-1 flex flex-col justify-between">
                      <div className="h-[230px] w-full mt-2 font-mono text-xs select-none">
                        {(() => {
                          const thresholds = (returnPeriodsData as Record<string, any>)[stationDetail.station_name] || {
                            watch: stationDetail.rp_2,
                            warning: stationDetail.rp_5,
                            danger: stationDetail.rp_15,
                            extreme: stationDetail.rp_20
                          };
                          
                          // Find min/max for chart Y-axis domain
                          const validFlows = chartData.map(d => d.streamflow).filter(v => v !== null) as number[];
                          const currentMin = validFlows.length > 0 ? Math.min(...validFlows) : 0;
                          const currentMax = validFlows.length > 0 ? Math.max(...validFlows) : 10;
                          
                          const watchVal = thresholds.watch || 10;
                          const extremeVal = thresholds.extreme || 100;
                          const yMin = Math.max(0, Math.round(Math.min(currentMin, watchVal * 0.5)));
                          const yMax = Math.round(Math.max(currentMax, extremeVal * 1.1));

                          return (
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis 
                                  dataKey="displayDate" 
                                  stroke="#94a3b8" 
                                  fontSize={10} 
                                  tickLine={false} 
                                />
                                <YAxis 
                                  domain={[yMin, yMax]} 
                                  stroke="#94a3b8" 
                                  fontSize={10} 
                                  tickLine={false} 
                                  axisLine={false} 
                                />
                                <ChartTooltip
                                  contentStyle={{ backgroundColor: "#0a3d62", border: "none", borderRadius: "8px", color: "#fff" }}
                                  labelStyle={{ fontWeight: "bold" }}
                                  formatter={(value: any) => [`${value} m³/s`, "Streamflow"]}
                                />
                                
                                {thresholds.watch && (
                                  <ReferenceLine y={thresholds.watch} stroke="#2563eb" strokeDasharray="3 3" strokeWidth={1} />
                                )}
                                {thresholds.warning && (
                                  <ReferenceLine y={thresholds.warning} stroke="#d97706" strokeDasharray="3 3" strokeWidth={1} />
                                )}
                                {thresholds.danger && (
                                  <ReferenceLine y={thresholds.danger} stroke="#ea580c" strokeDasharray="3 3" strokeWidth={1} />
                                )}
                                {thresholds.extreme && (
                                  <ReferenceLine y={thresholds.extreme} stroke="#e11d48" strokeDasharray="3 3" strokeWidth={1.5} />
                                )}

                                <Line
                                  type="monotone"
                                  dataKey="streamflow"
                                  stroke="#0a3d62"
                                  strokeWidth={2.5}
                                  dot={{ r: 4, fill: "#0a3d62", strokeWidth: 1 }}
                                  activeDot={{ r: 6, fill: "#ea580c" }}
                                  connectNulls={false}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          );
                        })()}
                      </div>
                      
                      <div className="flex flex-wrap items-center justify-center gap-3 mt-3 text-[10px] font-bold font-mono">
                        <span className="flex items-center gap-1"><span className="w-2.5 h-1.5 bg-[#2563eb] rounded"></span> Watch</span>
                        <span className="flex items-center gap-1"><span className="w-2.5 h-1.5 bg-[#d97706] rounded"></span> Warning</span>
                        <span className="flex items-center gap-1"><span className="w-2.5 h-1.5 bg-[#ea580c] rounded"></span> Danger</span>
                        <span className="flex items-center gap-1"><span className="w-2.5 h-1.5 bg-[#e11d48] rounded"></span> Extreme</span>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Streamflow History */}
                <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 overflow-hidden">
                  <CardHeader className="border-b border-gray-100 flex flex-row items-center justify-between py-4">
                    <div>
                      <CardTitle className="text-lg text-gray-800">Streamflow Records</CardTitle>
                      <p className="text-sm text-gray-500 mt-0.5">Recent predictions and observed states</p>
                    </div>
                    <button 
                      onClick={() => fetchStationDetail(stationDetail.station_id)}
                      className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                      disabled={detailLoading}
                      title="Refresh table"
                    >
                      <RefreshCw className={`w-4 h-4 text-gray-500 ${detailLoading ? 'animate-spin' : ''}`} />
                    </button>
                  </CardHeader>
                  <CardContent className="p-0">
                    {stationDetail.recent_predictions.length === 0 ? (
                      <div className="p-8 text-center text-gray-500">
                        No predictions recorded for this station yet.
                      </div>
                    ) : (
                      <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                            <tr>
                              <th className="text-left py-3 px-4 font-semibold text-gray-700">Date</th>
                              <th className="text-right py-3 px-4 font-semibold text-gray-700">Streamflow (m&sup3;/s)</th>
                              <th className="text-center py-3 px-4 font-semibold text-gray-700">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {stationDetail.recent_predictions.map((row, idx) => (
                              <tr key={idx} className="border-b border-gray-100 hover:bg-blue-50/50 transition-colors">
                                <td className="py-3 px-4 font-medium text-gray-900">{row.date}</td>
                                <td className="py-3 px-4 text-right font-bold text-[#0a3d62]">
                                  {row.raw_streamflow.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                                </td>
                                <td className="py-3 px-4 text-center">
                                  {(() => {
                                    const risk = getRiskStatus(row.raw_streamflow, stationDetail);
                                    return (
                                      <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold ${risk.lightClass}`}>
                                        {risk.label}
                                      </span>
                                    );
                                  })()}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* ── Prediction Output ── */}
                {predResult && (
                  <div className="flex flex-col gap-6 animate-fade-in">
                    {/* Model Output Summary Card */}
                    <Card className="bg-gradient-to-br from-[#0a3d62] to-[#1a5276] rounded-2xl shadow-2xl border-0 text-white overflow-hidden">
                      <CardHeader className="pb-3 pt-5 px-6">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-lg font-bold text-white/90 tracking-wide">
                            Model Output — {predResult.date}
                          </CardTitle>
                          <span className="text-xs bg-white/20 text-white px-2.5 py-1 rounded-full font-semibold">
                            LSTM + XGBoost
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="px-6 pb-6">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          {/* Predicted Streamflow */}
                          <div className="bg-white/10 rounded-xl p-4 flex flex-col gap-1">
                            <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Predicted Flow</p>
                            <p className="text-2xl font-bold text-white">
                              {predResult.pred_raw_streamflow.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                            </p>
                            <p className="text-xs text-white/50">m³/s</p>
                          </div>
                          {/* Delta */}
                          <div className="bg-white/10 rounded-xl p-4 flex flex-col gap-1">
                            <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Δ Change</p>
                            <p className={`text-2xl font-bold ${predResult.pred_delta_raw >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                              {predResult.pred_delta_raw >= 0 ? '+' : ''}{predResult.pred_delta_raw.toFixed(1)}
                            </p>
                            <p className="text-xs text-white/50">m³/s vs. anchor</p>
                          </div>
                          {/* Anchor */}
                          <div className="bg-white/10 rounded-xl p-4 flex flex-col gap-1">
                            <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Anchor (t−1)</p>
                            <p className="text-2xl font-bold text-white/80">
                              {predResult.anchor_streamflow.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                            </p>
                            <p className="text-xs text-white/50">m³/s (yesterday)</p>
                          </div>
                          {/* Rainfall fetched */}
                          <div className="bg-white/10 rounded-xl p-4 flex flex-col gap-1">
                            <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Today's Rainfall</p>
                            <p className="text-2xl font-bold text-sky-300">
                              {predResult.rainfall_mm_fetched.toFixed(2)}
                            </p>
                            <p className="text-xs text-white/50">mm (Open-Meteo)</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* ── Future Trajectory Output ── */}
                {trajectory && (
                  <div className="flex flex-col gap-6 animate-fade-in">
                    <Card className="bg-gradient-to-br from-indigo-700 to-indigo-900 rounded-2xl shadow-2xl border-0 text-white overflow-hidden">
                      <CardHeader className="pb-3 pt-5 px-6">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-lg font-bold text-white/90 tracking-wide">
                            Forecast Trajectory (Unsaved)
                          </CardTitle>
                          <span className="text-xs bg-white/20 text-white px-2.5 py-1 rounded-full font-semibold">
                            Simulated Future
                          </span>
                        </div>
                        <p className="text-sm text-indigo-200 mt-1">
                          Forward-chained predictions calling actual Open-Meteo forecasts.
                        </p>
                      </CardHeader>
                      <CardContent className="px-0 pb-0">
                        <div className="overflow-x-auto w-full">
                          <table className="w-full text-sm">
                            <thead className="bg-indigo-950/40 text-left border-b border-indigo-500/30">
                              <tr>
                                <th className="py-3 px-6 font-semibold text-indigo-100">Forecast Date</th>
                                <th className="py-3 px-6 font-semibold text-indigo-100">Anchor (m³/s)</th>
                                <th className="py-3 px-6 font-semibold text-indigo-100">Forecast Rain</th>
                                <th className="py-3 px-6 font-semibold text-indigo-100">Predicted Δ</th>
                                <th className="py-3 px-6 font-semibold text-indigo-100 text-right">Predicted Flow</th>
                                <th className="py-3 px-6 font-semibold text-indigo-100 text-center">Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {trajectory.map((step, idx) => (
                                <tr key={idx} className="border-b border-indigo-500/10 hover:bg-white/5 transition-colors">
                                  <td className="py-3 px-6 font-medium text-white">{step.date}</td>
                                  <td className="py-3 px-6 text-indigo-200">{step.anchor_streamflow.toFixed(1)}</td>
                                  <td className="py-3 px-6 text-indigo-200">{step.rainfall_mm_fetched.toFixed(2)} mm</td>
                                  <td className={`py-3 px-6 font-bold ${step.pred_delta_raw >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {step.pred_delta_raw >= 0 ? '+' : ''}{step.pred_delta_raw.toFixed(1)}
                                  </td>
                                  <td className="py-3 px-6 text-right font-bold text-white text-lg">
                                    {step.pred_raw_streamflow.toFixed(1)}
                                  </td>
                                  <td className="py-3 px-6 text-center">
                                    {(() => {
                                      const risk = getRiskStatus(step.pred_raw_streamflow, stationDetail);
                                      return (
                                        <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold ${risk.darkClass}`}>
                                          {risk.label}
                                        </span>
                                      );
                                    })()}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* 15-Day Rainfall Window Table */}
                {rainWindow && (
                  <div className="flex flex-col gap-6 animate-fade-in mt-2">
                    <Card className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-gray-100 overflow-hidden">
                      <CardHeader className="border-b border-gray-100 py-4 px-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="text-base text-gray-800">15-Day Rainfall Input Window</CardTitle>
                            <p className="text-xs text-gray-400 mt-0.5">Antecedent rainfall (mm/day) fed to the model for each lag day</p>
                          </div>
                          <span className="text-xs bg-sky-100 text-sky-700 px-2.5 py-1 rounded-full font-semibold">
                            Lag −14d → target
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead className="sticky top-0 bg-sky-50 border-b border-sky-100 z-10">
                              <tr>
                                <th className="text-left py-2.5 px-4 font-semibold text-sky-800">Lag</th>
                                <th className="text-left py-2.5 px-4 font-semibold text-sky-800">Date</th>
                                <th className="text-right py-2.5 px-4 font-semibold text-sky-800">Rainfall (mm)</th>
                                <th className="py-2.5 px-4 font-semibold text-sky-800">Bar</th>
                              </tr>
                            </thead>
                            <tbody>
                              {rainWindow.map((row, idx) => {
                                const maxRain = Math.max(...rainWindow.map(r => r.rainfall_mm), 1);
                                const barPct = Math.round((row.rainfall_mm / maxRain) * 100);
                                const isTarget = idx === rainWindow.length - 1;
                                return (
                                  <tr
                                    key={row.date}
                                    className={`border-b border-gray-100 transition-colors ${isTarget ? 'bg-sky-50' : 'hover:bg-gray-50'}`}
                                  >
                                    <td className="py-2 px-4 font-mono text-xs text-gray-500">
                                      {isTarget ? <span className="font-bold text-sky-700">t=0</span> : `t−${14 - idx}`}
                                    </td>
                                    <td className={`py-2 px-4 font-medium ${isTarget ? 'text-sky-700 font-bold' : 'text-gray-700'}`}>
                                      {row.date}
                                      {isTarget && <span className="ml-2 text-[10px] bg-sky-200 text-sky-800 px-1.5 py-0.5 rounded-full font-semibold">TARGET</span>}
                                    </td>
                                    <td className="py-2 px-4 text-right font-bold text-[#0a3d62]">
                                      {row.rainfall_mm.toFixed(2)}
                                    </td>
                                    <td className="py-2 px-4 w-32">
                                      <div className="bg-gray-100 rounded-full h-2 w-full">
                                        <div
                                          className="bg-sky-400 h-2 rounded-full transition-all"
                                          style={{ width: `${barPct}%` }}
                                        />
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Developer Debug Feature Dump (collapsed by default) */}
                    {debugFeatures && (
                      <details className="group">
                        <summary className="cursor-pointer list-none">
                          <Card className="bg-white rounded-2xl shadow border border-dashed border-amber-300 hover:border-amber-400 transition-colors">
                            <CardHeader className="bg-amber-50 rounded-2xl py-3 px-5 flex flex-row items-center justify-between">
                              <CardTitle className="text-sm text-amber-900 font-semibold">
                                🛠 Developer: Full Feature Dump
                              </CardTitle>
                              <span className="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded font-mono group-open:hidden">
                                Click to expand
                              </span>
                              <span className="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded font-mono hidden group-open:inline">
                                Click to collapse
                              </span>
                            </CardHeader>
                          </Card>
                        </summary>
                        <div className="mt-1 rounded-2xl border border-dashed border-amber-300 overflow-hidden">
                          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                            <table className="w-full text-sm font-mono">
                              <thead className="sticky top-0 bg-amber-100 border-b border-amber-200 z-10 text-amber-900">
                                <tr>
                                  <th className="text-left py-2 px-4 font-semibold">Feature Name</th>
                                  <th className="text-right py-2 px-4 font-semibold">Value (Row 15)</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(debugFeatures).map(([key, val], idx) => (
                                  <tr key={key} className={`border-b border-amber-50 hover:bg-amber-50 transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                                    <td className="py-2 px-4 text-gray-700">{key}</td>
                                    <td className="py-2 px-4 text-right font-medium text-blue-900">
                                      {typeof val === 'number' ? (val % 1 !== 0 ? val.toFixed(4) : val) : val}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </details>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Interactive Master Predict Summary Modal */}
        {reportModalOpen && masterPredictData && (
          <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in p-4">
            <div className="bg-white rounded-3xl shadow-2xl max-w-4xl w-full border border-gray-100 flex flex-col max-h-[85vh] overflow-hidden transform transition-all animate-scale-in">
              {/* Modal Header */}
              <div className="bg-gradient-to-r from-[#0a3d62] to-[#12588c] text-white py-5 px-6 flex items-center justify-between border-b border-gray-100 flex-shrink-0">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">
                    District Forecast Report: {selectedDistrict}
                  </h3>
                  <p className="text-xs text-sky-200 mt-1">
                    Peak streamflow severities for next 7 days (July 15 - July 21, 2026)
                  </p>
                </div>
                <button
                  onClick={() => setReportModalOpen(false)}
                  className="text-white/80 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
                >
                  Close
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-6">
                {/* Stats Summary row */}
                {(() => {
                  const summaries = Object.entries(masterPredictData).map(([id, val]) => getPeakSeverity(Number(id), val));
                  const counts = { NORMAL: 0, WATCH: 0, WARNING: 0, DANGER: 0, EXTREME: 0 };
                  summaries.forEach(s => {
                    counts[s.label as keyof typeof counts] = (counts[s.label as keyof typeof counts] || 0) + 1;
                  });
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div 
                        onClick={() => setFilterSeverity(filterSeverity === "NORMAL" ? null : "NORMAL")}
                        className={`cursor-pointer hover:scale-105 transition-all p-3 border rounded-xl flex flex-col items-center justify-center shadow-sm ${
                          filterSeverity === "NORMAL" 
                            ? "bg-emerald-100 border-emerald-300 ring-2 ring-emerald-500/30 scale-105" 
                            : "bg-emerald-50 border-emerald-100"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-emerald-700 uppercase">Normal</span>
                        <p className="text-2xl font-black text-emerald-900 mt-1">{counts.NORMAL}</p>
                      </div>
                      <div 
                        onClick={() => setFilterSeverity(filterSeverity === "WATCH" ? null : "WATCH")}
                        className={`cursor-pointer hover:scale-105 transition-all p-3 border rounded-xl flex flex-col items-center justify-center shadow-sm ${
                          filterSeverity === "WATCH" 
                            ? "bg-blue-100 border-blue-300 ring-2 ring-blue-500/30 scale-105" 
                            : "bg-blue-50 border-blue-100"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-blue-700 uppercase">Watch</span>
                        <p className="text-2xl font-black text-blue-900 mt-1">{counts.WATCH}</p>
                      </div>
                      <div 
                        onClick={() => setFilterSeverity(filterSeverity === "WARNING" ? null : "WARNING")}
                        className={`cursor-pointer hover:scale-105 transition-all p-3 border rounded-xl flex flex-col items-center justify-center shadow-sm ${
                          filterSeverity === "WARNING" 
                            ? "bg-amber-100 border-amber-300 ring-2 ring-amber-500/30 scale-105" 
                            : "bg-amber-50 border-amber-100"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-amber-700 uppercase">Warning</span>
                        <p className="text-2xl font-black text-amber-900 mt-1">{counts.WARNING}</p>
                      </div>
                      <div 
                        onClick={() => setFilterSeverity(filterSeverity === "DANGER" ? null : "DANGER")}
                        className={`cursor-pointer hover:scale-105 transition-all p-3 border rounded-xl flex flex-col items-center justify-center shadow-sm ${
                          filterSeverity === "DANGER" 
                            ? "bg-orange-100 border-orange-300 ring-2 ring-orange-500/30 scale-105" 
                            : "bg-orange-50 border-orange-100"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-orange-700 uppercase">Danger</span>
                        <p className="text-2xl font-black text-orange-950 mt-1">{counts.DANGER}</p>
                      </div>
                      <div 
                        onClick={() => setFilterSeverity(filterSeverity === "EXTREME" ? null : "EXTREME")}
                        className={`cursor-pointer hover:scale-105 transition-all p-3 border rounded-xl flex flex-col items-center justify-center shadow-sm col-span-2 md:col-span-1 ${
                          filterSeverity === "EXTREME" 
                            ? "bg-rose-100 border-rose-300 ring-2 ring-rose-500/30 scale-105" 
                            : "bg-rose-50 border-rose-100"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-rose-700 uppercase">Extreme</span>
                        <p className="text-2xl font-black text-rose-900 mt-1">{counts.EXTREME}</p>
                      </div>
                    </div>
                  );
                })()}

                {/* Stations Details List */}
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-gray-700">Station-wise Details (Click to select)</h4>
                    <span className="text-xs text-gray-400 font-medium">
                      {filterSeverity 
                        ? `Filtered: ${filterSeverity} list` 
                        : "Showing Watch and higher by default"}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(masterPredictData).map(([idStr, val]) => {
                      const id = Number(idStr);
                      const station = stations.find(s => s.station_id === id);
                      if (!station) return null;
                      
                      const info = gaugeLookup[station.station_name];
                      const severity = getPeakSeverity(id, val);
                      
                      // 1. If a filter is selected, filter strictly
                      if (filterSeverity) {
                        if (severity.label !== filterSeverity) return null;
                      } else {
                        // 2. Default: Watch and higher (level >= 2)
                        if (severity.level < 2) return null;
                      }
                      
                      return (
                        <div
                          key={id}
                          onClick={() => {
                            setSelectedStationId(id);
                            setReportModalOpen(false);
                          }}
                          className="border border-gray-100 rounded-xl p-4 bg-gray-50 hover:bg-indigo-50/40 hover:border-indigo-200 transition-all cursor-pointer flex flex-col justify-between gap-3 group"
                        >
                          <div className="flex flex-col">
                            <h5 className="font-bold text-gray-800 group-hover:text-indigo-950 transition-colors">
                              {info?.location_name || station.station_name}
                            </h5>
                            <span className="text-[10px] text-gray-400 mt-0.5">
                              {info ? `${info.sub_district}, ${info.district}` : "Unknown location"} (ID: {id})
                            </span>
                          </div>
                          
                          {/* Mini Sparkline Chart */}
                          {severity.chartData && (
                            <div className="h-[60px] w-full border border-gray-200/50 rounded-lg p-1 bg-white">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={severity.chartData} margin={{ top: 2, right: 2, left: -35, bottom: 2 }}>
                                  <YAxis domain={['auto', 'auto']} tick={false} axisLine={false} />
                                  <Line
                                    type="monotone"
                                    dataKey="streamflow"
                                    stroke="#0a3d62"
                                    strokeWidth={1.5}
                                    dot={false}
                                    connectNulls={false}
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          )}
                          
                          <div className="flex items-center justify-between border-t border-gray-200/50 pt-2.5">
                            <div className="flex flex-col">
                              <span className="text-[9px] uppercase font-bold text-gray-400">Peak Flow</span>
                              <span className="text-sm font-bold text-gray-700 mt-0.5">
                                {severity.peakFlow.toLocaleString(undefined, { maximumFractionDigits: 1 })} m³/s
                              </span>
                              {severity.peakDate && (
                                <span className="text-[9px] text-gray-400 font-mono mt-0.5">on {format(new Date(severity.peakDate), "MMM dd")}</span>
                              )}
                            </div>
                            <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded-full border ${severity.color}`}>
                              {severity.label}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              
              {/* Modal Footer */}
              <div className="bg-gray-50 py-4 px-6 border-t border-gray-100 flex items-center justify-between flex-shrink-0">
                <span className="text-xs text-gray-500 font-medium">
                  Click on any station card above to view it in full detail on the dashboard.
                </span>
                <button
                  onClick={() => {
                    // Export to CSV
                    const rows = [["Station ID", "Station Name", "Location", "Sub-district", "District", "Peak Flow (m3/s)", "Peak Date", "Severity"]];
                    Object.entries(masterPredictData).forEach(([idStr, val]) => {
                      const id = Number(idStr);
                      const station = stations.find(s => s.station_id === id);
                      if (!station) return;
                      const info = gaugeLookup[station.station_name];
                      const severity = getPeakSeverity(id, val);
                      rows.push([
                        id.toString(),
                        station.station_name,
                        info?.location_name || "",
                        info?.sub_district || "",
                        info?.district || "",
                        severity.peakFlow.toString(),
                        severity.peakDate,
                        severity.label
                      ]);
                    });
                    
                    const csvContent = "data:text/csv;charset=utf-8," 
                      + rows.map(e => e.map(val => `"${val.replace(/"/g, '""')}"`).join(",")).join("\n");
                    const encodedUri = encodeURI(csvContent);
                    const link = document.createElement("a");
                    link.setAttribute("href", encodedUri);
                    link.setAttribute("download", `Master_Predict_${selectedDistrict}.csv`);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                  }}
                  className="bg-[#0a3d62] hover:bg-[#072a44] text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
                >
                  Export CSV
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
