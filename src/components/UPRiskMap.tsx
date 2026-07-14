import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Uttar Pradesh coordinates roughly
const UP_CENTER: [number, number] = [26.8467, 80.9462];
const DEFAULT_ZOOM = 6.5;

interface DistrictRiskData {
  risk: number;
  rainfall: number;
  alert: string;
  updateTime: string;
}

const mockRiskData: Record<string, DistrictRiskData> = {
  "Lucknow": { risk: 0.73, rainfall: 92, alert: "Moderate", updateTime: "Live" },
  "Kanpur": { risk: 0.81, rainfall: 110, alert: "High", updateTime: "Live" },
  "Varanasi": { risk: 0.43, rainfall: 55, alert: "Moderate", updateTime: "Live" },
  "Agra": { risk: 0.25, rainfall: 30, alert: "Low", updateTime: "Live" },
  "Allahabad": { risk: 0.65, rainfall: 78, alert: "Moderate", updateTime: "Live" },
  "Bareilly": { risk: 0.35, rainfall: 45, alert: "Low", updateTime: "Live" },
  "Ghaziabad": { risk: 0.15, rainfall: 20, alert: "Low", updateTime: "Live" },
  "Jhansi": { risk: 0.12, rainfall: 15, alert: "Low", updateTime: "Live" },
  "Gorakhpur": { risk: 0.88, rainfall: 125, alert: "High", updateTime: "Live" },
  "Aligarh": { risk: 0.48, rainfall: 62, alert: "Moderate", updateTime: "Live" },
};

const getRiskColor = (risk: number) => {
  if (risk >= 0.7) return '#ef4444'; // Red (High)
  if (risk >= 0.4) return '#f59e0b'; // Yellow (Moderate)
  return '#22c55e'; // Green (Low)
};

const DistrictLegend = () => {
  return (
    <div className="absolute bottom-4 left-4 z-[1000] bg-white/90 backdrop-blur-sm p-4 shadow-lg border border-gray-200 rounded-lg pointer-events-none">
      <h4 className="text-xs font-bold uppercase tracking-wider mb-3 text-gray-700">Flood Risk Level</h4>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#ef4444]" />
          <span className="text-xs font-medium text-gray-600">High Risk (0.7 - 1.0)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#f59e0b]" />
          <span className="text-xs font-medium text-gray-600">Moderate Risk (0.4 - 0.7)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#22c55e]" />
          <span className="text-xs font-medium text-gray-600">Low Risk (0.0 - 0.4)</span>
        </div>
      </div>
    </div>
  );
};

const UPRiskMap: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const [geoData, setGeoData] = useState<any>(null);

  useEffect(() => {
    fetch('/up_districts.geojson')
      .then(res => res.json())
      .then(data => setGeoData(data))
      .catch(err => console.error("Error loading GeoJSON:", err));
  }, []);

  useEffect(() => {
    if (!mapRef.current || leafletMap.current) return;

    // Initialize map
    const map = L.map(mapRef.current).setView(UP_CENTER, DEFAULT_ZOOM);
    leafletMap.current = map;

    // Add TileLayer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    return () => {
      if (leafletMap.current) {
        leafletMap.current.remove();
        leafletMap.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!leafletMap.current || !geoData) return;

    const geoJsonLayer = L.geoJSON(geoData, {
      style: (feature: any) => {
        const districtName = feature.properties.Name;
        const data = mockRiskData[districtName] || { risk: 0.2 };
        return {
          fillColor: getRiskColor(data.risk),
          weight: 1,
          opacity: 1,
          color: 'white',
          fillOpacity: 0.6,
        };
      },
      onEachFeature: (feature, layer) => {
        const districtName = feature.properties.Name;
        const data = mockRiskData[districtName] || { risk: 0.2, rainfall: 25, alert: "Low", updateTime: "N/A" };

        layer.on({
          mouseover: (e) => {
            const l = e.target;
            l.setStyle({
              weight: 3,
              color: '#ffffff',
              fillOpacity: 0.9,
            });
            l.bringToFront();
          },
          mouseout: (e) => {
            const l = e.target;
            l.setStyle({
              weight: 1,
              color: '#ffffff',
              fillOpacity: 0.6,
            });
          },
          click: (e) => {
            L.popup()
              .setLatLng(e.latlng)
              .setContent(`
                <div class="p-3 font-sans min-w-[180px]">
                  <h3 class="text-lg font-bold border-b border-gray-200 pb-2 mb-2 text-[#0a3d62]">${districtName}</h3>
                  <div class="space-y-1.5 text-sm">
                    <div class="flex justify-between">
                      <span class="text-gray-500">Flood Probability:</span>
                      <span class="font-bold font-mono text-gray-800">${data.risk.toFixed(2)}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-500">Rainfall Forecast:</span>
                      <span class="font-bold text-gray-800">${data.rainfall} mm</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-500">Alert Level:</span>
                      <span class="px-2 py-0.5 rounded text-[10px] uppercase font-bold text-white" style="background-color: ${getRiskColor(data.risk)}">
                        ${data.alert}
                      </span>
                    </div>
                    <div class="flex justify-between mt-2 pt-2 border-t border-gray-100 text-[10px] text-gray-400 italic">
                      <span>Last Updated:</span>
                      <span>${data.updateTime}</span>
                    </div>
                  </div>
                </div>
              `)
              .openOn(leafletMap.current!);
          }
        });
      }
    }).addTo(leafletMap.current);

    return () => {
      if (leafletMap.current && geoJsonLayer) {
        leafletMap.current.removeLayer(geoJsonLayer);
      }
    };
  }, [geoData]);

  return (
    <div className="relative w-full h-[500px] lg:h-[600px] bg-[#e1f0fa] overflow-hidden">
      <div 
        ref={mapRef} 
        style={{ height: '100%', width: '100%' }}
        className="z-0"
      />
      <DistrictLegend />
    </div>
  );
};

export default UPRiskMap;
