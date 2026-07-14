from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import httpx
import os
import sys
from datetime import date, datetime
from typing import Optional

from districts import UP_DISTRICT_NAMES
from heatwave_model import get_heatwave_predictions

# Add Flood_prediction and deploy to path
_flood_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Flood_prediction")
_deploy_dir = os.path.join(_flood_dir, "deploy")
if _flood_dir not in sys.path:
    sys.path.insert(0, _flood_dir)
if _deploy_dir not in sys.path:
    sys.path.insert(0, _deploy_dir)

# Import flood prediction modules (after path setup)
import database as flood_db
from seed_db import seed as seed_flood_db
from validate import run_validation
from scheduler import start_scheduler, stop_scheduler
from prediction_service import run_prediction_for_station

app = FastAPI(title="CRO Prediction API")


@app.on_event("startup")
def startup():
    """Initialize flood prediction system on startup."""
    try:
        # 1. Initialize and seed database
        flood_db.check_and_reset_database_if_needed()
        flood_db.init_tables()
        if flood_db.get_station_count() == 0:
            seed_flood_db()
            print("🌧️ Seeding complete. Running bootstrap rainfall history...")
            from bootstrap import bootstrap
            bootstrap()

        # 2. Run startup validation
        # run_validation()

        # 3. Start the daily scheduler
        start_scheduler()

        # 4. Asynchronously launch historical missing predictions auto-sync
        # import threading
        # from prediction_service import sync_historical_predictions
        # threading.Thread(target=sync_historical_predictions, daemon=True, name="AutoSyncThread").start()

        print("\n🌊 Flood Prediction system fully initialized!")
    except Exception as e:
        print(f"\n⚠️  Flood Prediction startup error: {e}")
        print("   The /predict endpoint may not work until this is resolved.")


@app.on_event("shutdown")
def shutdown():
    """Clean up scheduler on shutdown."""
    try:
        stop_scheduler()
    except Exception:
        pass

# Setup CORS for Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "http://localhost", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UP_DISTRICTS = {
    "Agra": (27.1767, 78.0081),
    "Aligarh": (27.8974, 78.0880),
    "Prayagraj": (25.4358, 81.8463),
    "Ambedkar Nagar": (26.4069, 82.5359),
    "Amethi": (26.1606, 81.8153),
    "Amroha": (28.8988, 78.4655),
    "Auraiya": (26.4674, 79.5161),
    "Ayodhya": (26.7915, 82.1979),
    "Azamgarh": (26.0691, 82.9723),
    "Baghpat": (28.9416, 77.2687),
    "Bahraich": (27.5755, 81.5947),
    "Ballia": (25.7537, 84.1448),
    "Balrampur": (27.4294, 82.1764),
    "Banda": (25.4740, 80.3396),
    "Barabanki": (26.9272, 81.1895),
    "Bareilly": (28.3670, 79.4304),
    "Basti": (26.8047, 82.7214),
    "Bhadohi": (25.3956, 82.5707),
    "Bijnor": (29.3724, 78.1358),
    "Budaun": (28.0287, 79.1245),
    "Bulandshahr": (28.4069, 77.8496),
    "Chandauli": (25.2678, 83.2671),
    "Chitrakoot": (25.1052, 80.9595),
    "Deoria": (26.5050, 83.7840),
    "Etah": (27.6256, 78.6653),
    "Etawah": (26.7845, 79.0205),
    "Farrukhabad": (27.3826, 79.6200),
    "Fatehpur": (25.9332, 80.8256),
    "Firozabad": (27.1517, 78.3965),
    "Gautam Buddha Nagar": (28.4089, 77.3178),
    "Ghaziabad": (28.6692, 77.4538),
    "Ghazipur": (25.5786, 83.5852),
    "Gonda": (27.1345, 81.9680),
    "Gorakhpur": (26.7606, 83.3732),
    "Hamirpur": (25.9526, 80.1504),
    "Hapur": (28.7306, 77.7759),
    "Hardoi": (27.3912, 80.1264),
    "Hathras": (27.5997, 78.0531),
    "Jalaun": (26.1420, 79.3514),
    "Jaunpur": (25.7464, 82.6837),
    "Jhansi": (25.4484, 78.5685),
    "Kannauj": (27.0503, 79.9197),
    "Kanpur Dehat": (26.3116, 79.9575),
    "Kanpur Nagar": (26.4499, 80.3319),
    "Kasganj": (27.8118, 78.6473),
    "Kaushambi": (25.5393, 81.4284),
    "Lakhimpur Kheri": (27.9438, 80.7719),
    "Kushinagar": (26.7447, 83.8966),
    "Lalitpur": (24.6859, 78.4069),
    "Lucknow": (26.8467, 80.9462),
    "Maharajganj": (27.1436, 83.5630),
    "Mahoba": (25.2952, 79.8732),
    "Mainpuri": (27.2272, 79.0304),
    "Mathura": (27.4924, 77.6737),
    "Mau": (25.9366, 83.5639),
    "Meerut": (28.9845, 77.7064),
    "Mirzapur": (25.1458, 82.5645),
    "Moradabad": (28.8386, 78.7733),
    "Muzaffarnagar": (29.4727, 77.7085),
    "Pilibhit": (28.6360, 79.8055),
    "Pratapgarh": (25.9184, 81.8211),
    "Raebareli": (26.2238, 81.2403),
    "Rampur": (28.8153, 79.0255),
    "Saharanpur": (29.9695, 77.5450),
    "Sambhal": (28.5866, 78.5714),
    "Sant Kabir Nagar": (26.7327, 83.0577),
    "Shahjahanpur": (27.8805, 79.9126),
    "Shamli": (29.4443, 77.3106),
    "Shravasti": (27.7019, 81.8596),
    "Siddharthnagar": (27.2947, 82.8227),
    "Sitapur": (27.5627, 80.6811),
    "Sonbhadra": (24.6826, 83.0645),
    "Sultanpur": (26.2573, 82.0734),
    "Unnao": (26.5413, 80.4870),
    "Varanasi": (25.3176, 82.9739)
}

API_KEY = "PLACEHOLDER_PIRATE_API_KEY"


class PredictionRequest(BaseModel):
    district: str
    model_slug: str


class FloodPredictionRequest(BaseModel):
    station_id: int
    date: str  # ISO format: "2026-03-28"
    client_rainfall_data: Optional[dict[str, float]] = None


class AdminSyncRainfallRequest(BaseModel):
    # Dictionary mapping station_id (str or int) to a dict of date -> rainfall_mm
    station_data: dict[str, dict[str, float]]


@app.get("/api/districts")
def get_districts():
    return {"districts": sorted(list(UP_DISTRICTS.keys()))}


@app.get("/heatwave-risk-up")
def heatwave_risk_up():
    """Return simulated heatwave risk predictions for all 75 UP districts."""
    try:
        predictions = get_heatwave_predictions(UP_DISTRICT_NAMES)
        return {"districts": predictions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
async def predict_risk(req: PredictionRequest):
    if req.district not in UP_DISTRICTS:
        raise HTTPException(status_code=400, detail="Invalid district")
    
    lat, lng = UP_DISTRICTS[req.district]
    
    # ── API call to Open-Meteo ──
    meteo_data = {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&daily=temperature_2m_max,wind_speed_10m_max,rain_sum,precipitation_sum&current=wind_speed_10m"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                # Extract simple summary data (taking the first day/current)
                meteo_data = {
                    "current_wind_speed": data.get("current", {}).get("wind_speed_10m"),
                    "max_temp": data.get("daily", {}).get("temperature_2m_max", [None])[0],
                    "max_wind": data.get("daily", {}).get("wind_speed_10m_max", [None])[0],
                    "rain_sum": data.get("daily", {}).get("rain_sum", [None])[0],
                    "precip_sum": data.get("daily", {}).get("precipitation_sum", [None])[0]
                }
    except Exception as e:
        print("Failed to fetch from OpenMeteo:", e)
    
    # ── Hazard-Specific Dummy Model Logic ──
    # Default to random if API fails
    base_prob = random.uniform(20.0, 40.0) 
    
    if meteo_data:
        if req.model_slug == "heatwave-analysis":
            temp = meteo_data.get("max_temp") or 25
            # Heatwave risk increases significantly above 35°C
            base_prob = min(98.0, max(5.0, (temp - 25) * 4 + random.uniform(-5, 5)))
        elif req.model_slug in ["flood-risk", "precipitation-modeling"]:
            precip = meteo_data.get("precip_sum") or 0
            # Risk increases with precipitation
            base_prob = min(95.0, max(10.0, (precip * 5) + random.uniform(0, 15)))
        elif req.model_slug == "watershed-management": # Lightning Prediction
            wind = meteo_data.get("max_wind") or 10
            # Higher winds often correlate with storm systems/lightning
            base_prob = min(92.0, max(8.0, (wind * 1.5) + random.uniform(5, 10)))
        elif req.model_slug == "coldwave-impact":
            temp = meteo_data.get("max_temp") or 25
            # Risk increases as temperature drops below 15°C
            base_prob = min(96.0, max(5.0, (20 - temp) * 5 + random.uniform(-10, 10)))

    probability = round(base_prob, 1)
    
    # Risk Level determination
    if probability < 30:
        level = "Low"
    elif probability < 60:
        level = "Medium"
    elif probability < 85:
        level = "High"
    else:
        level = "Extreme"
        
    return {
        "district": req.district,
        "model_slug": req.model_slug,
        "latitude": lat,
        "longitude": lng,
        "probability": probability,
        "risk_level": level,
        "meteo_data": meteo_data,
        "note": "Output is structurally randomized as a dummy model."
    }


# ═══════════════════════════════════════════════════════════════════════
# FLOOD STREAMFLOW PREDICTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/predict")
def predict_flood(req: FloodPredictionRequest):
    """
    Predict streamflow for a given station and date.
    Uses the LSTM + XGBoost hybrid model with real-time rainfall data.
    """
    try:
        target_date = date.fromisoformat(req.date)
        if target_date > date.today():
            from prediction_service import predict_future_streamflow
            result = predict_future_streamflow(req.station_id, target_date, client_rainfall=req.client_rainfall_data)
        else:
            result = run_prediction_for_station(req.station_id, target_date, client_rainfall=req.client_rainfall_data)
            
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        with open("backend/_api_crash.txt", "w") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/stations")
def list_stations():
    """List all 367 flood monitoring stations."""
    try:
        stations = flood_db.get_all_stations()
        return {
            "count": len(stations),
            "stations": [
                {
                    "station_id": s["station_id"],
                    "station_name": s["station_name"],
                    "latitude": s["latitude"],
                    "longitude": s["longitude"],
                }
                for s in stations
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/station/{station_id}")
def get_station_detail(station_id: int):
    """Get detailed info for a specific station."""
    try:
        station = flood_db.get_station(station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
        
        # Get latest gauge state
        flow_rows = flood_db.get_gauge_state(station_id, limit=5)
        
        return {
            **dict(station),
            "recent_predictions": [
                {"date": r["date"], "raw_streamflow": r["raw_streamflow"]}
                for r in flow_rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/sync-rainfall")
def admin_sync_rainfall(req: AdminSyncRainfallRequest):
    """
    Endpoint for local bootstrap script to bulk insert historical rainfall.
    Bypasses the need for Render backend to make Open-Meteo calls.
    """
    try:
        total_inserted = 0
        for station_id_str, daily_data in req.station_data.items():
            station_id = int(station_id_str)
            for date_str, rain_val in daily_data.items():
                flood_db.insert_rainfall(station_id, date_str, float(rain_val))
                total_inserted += 1
        return {"success": True, "records_inserted": total_inserted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
