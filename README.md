# 🌡️ VAE Weather Coldwave Analysis Application

A full-stack application for analyzing weather patterns and detecting coldwaves using a Variational Autoencoder (VAE) deep learning model.

## 🎯 Overview

This application combines a **FastAPI backend** with a **React frontend** to provide real-time coldwave detection based on weather data. The system uses a trained VAE model to identify anomalous weather patterns that indicate coldwave conditions.

## 🏗️ Architecture

```
crowebsite/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── main.py         # API endpoints and server
│   │   ├── model.py        # VAE model architecture
│   │   ├── artifacts/
│   │   │   └── vae_weather.pth  # Trained model weights
│   │   └── __init__.py
│   ├── requirements.txt    # Python dependencies
│   └── README.md          # Backend documentation
├── src/                    # React Frontend
│   ├── pages/
│   │   └── Projects.tsx   # Main UI with coldwave analysis
│   └── ...
├── start.bat              # Windows startup script
└── package.json           # Frontend dependencies
```

## ✨ Features

### Backend (FastAPI)
- ✅ **VAE Model Loading**: Automatic model initialization on startup
- ✅ **Coldwave Detection**: Anomaly detection using reconstruction error
- ✅ **REST API**: Well-documented endpoints with Swagger UI
- ✅ **CORS Support**: Configured for local development
- ✅ **Health Checks**: Monitor service status

### Frontend (React + TypeScript)
- ✅ **Interactive UI**: Modern, responsive design with Framer Motion animations
- ✅ **Real-time Analysis**: Send weather data and get instant results
- ✅ **Visual Feedback**: Color-coded alerts for coldwave detection
- ✅ **Data Visualization**: Display reconstruction, latent vectors, and metrics
- ✅ **Error Handling**: User-friendly error messages

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Node.js 16+** - [Download](https://nodejs.org/)
- **Git** - [Download](https://git-scm.com/)

### Option 1: Automated Setup (Windows)

Simply double-click `start.bat` or run:

```bash
start.bat
```

This will:
1. Check for Python and Node.js
2. Create a virtual environment
3. Install all dependencies
4. Start both servers in separate windows

### Option 2: Manual Setup

#### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment:**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to project root:**
   ```bash
   cd ..
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

## 🌐 Access the Application

Once both servers are running:

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📊 How It Works

### VAE Model Architecture

```
Input (5 features) → Encoder (64→32) → Latent Space (8D) → Decoder (32→64) → Output (5 features)
```

**Input Features:**
- Minimum Temperature (°C)
- Maximum Temperature (°C)
- Humidity (%)
- Wind Speed (m/s)
- Pressure (hPa)

### Coldwave Detection Logic

1. **Encoding**: Weather features are compressed into an 8-dimensional latent space
2. **Decoding**: The model reconstructs the original features
3. **Error Calculation**: Mean Squared Error (MSE) between input and reconstruction
4. **Detection**: High reconstruction error indicates anomalous patterns (coldwave)
5. **Threshold**: Default threshold is 5.0 (adjustable in `backend/app/main.py`)

### Example Request

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "minimum_temperature": 4.2,
      "maximum_temperature": 12.1,
      "humidity": 78,
      "wind_speed": 6.5,
      "pressure": 1014
    }
  }'
```

### Example Response

```json
{
  "reconstruction": {
    "minimum_temperature": 4.15,
    "maximum_temperature": 12.05,
    "humidity": 77.8,
    "wind_speed": 6.48,
    "pressure": 1013.9
  },
  "latent_vector": [0.234, -0.567, 0.891, 0.123, -0.456, 0.789, 0.012, -0.345],
  "reconstruction_error": 0.0234,
  "is_coldwave": false,
  "coldwave_confidence": 0.468
}
```

## 🎨 Using the Frontend

1. **Navigate to Projects Section**: The coldwave analysis is in the "Projects" page
2. **Find Coldwave Analysis Card**: Look for the card with the ❄️ icon
3. **Click "Run Coldwave VAE Analysis"**: This expands the analysis panel
4. **Edit Weather Data**: Modify the JSON input with your weather features
5. **Run Analysis**: Click "Run Analysis" to send data to the backend
6. **View Results**: See the coldwave detection status, reconstruction error, and latent vectors

## 🔧 Configuration

### Backend Configuration

Edit `backend/app/main.py` to adjust:

- **Coldwave Threshold**: Change `COLDWAVE_THRESHOLD` (default: 5.0)
- **CORS Origins**: Add/remove allowed frontend URLs
- **Model Path**: Update `MODEL_PATH` if needed

### Frontend Configuration

The frontend uses environment variables. Create a `.env` file in the project root:

```env
VITE_BACKEND_URL=http://localhost:8000
```

## 📦 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| POST | `/predict` | Weather analysis |
| POST | `/api/analyze-coldwave` | Coldwave analysis (alias) |
| GET | `/docs` | Swagger UI documentation |

## 🧪 Testing

### Test the Backend

```bash
# Health check
curl http://localhost:8000/health

# Coldwave analysis
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"features": {"minimum_temperature": 2.0, "maximum_temperature": 8.0, "humidity": 85, "wind_speed": 10.0, "pressure": 1010}}'
```

### Test the Frontend

1. Open http://localhost:5173
2. Navigate to the Projects section
3. Click on "Coldwave Analysis"
4. Use the interactive form to test different weather scenarios

## 🐛 Troubleshooting

### Backend Issues

**Model Not Loading:**
- Verify `backend/app/artifacts/vae_weather.pth` exists
- Check model architecture matches saved weights
- Ensure PyTorch is installed correctly

**Port 8000 Already in Use:**
```bash
# Use a different port
uvicorn app.main:app --reload --port 8001

# Update frontend .env file
VITE_BACKEND_URL=http://localhost:8001
```

### Frontend Issues

**CORS Errors:**
- Ensure backend is running
- Check CORS origins in `backend/app/main.py`
- Verify `VITE_BACKEND_URL` is correct

**Dependencies Not Installing:**
```bash
# Clear cache and reinstall
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

## 📚 Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PyTorch** - Deep learning framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Framer Motion** - Animations
- **Tailwind CSS** - Styling

## 🤝 Contributing

This is a project for the Climate Resilience Observatory (CRO) in Uttar Pradesh.

## 📄 License

This project is part of the CRO Website application.

## 🎓 Model Information

The VAE model was trained on historical weather data to learn normal weather patterns. When presented with new data:
- **Low reconstruction error** = Normal weather patterns
- **High reconstruction error** = Anomalous patterns (potential coldwave)

The model uses an 8-dimensional latent space to capture the essential features of weather patterns, making it efficient for real-time analysis.

## 🔮 Future Enhancements

- [ ] Historical data visualization
- [ ] Multi-day forecasting
- [ ] Model retraining interface
- [ ] Export analysis reports
- [ ] Email/SMS alerts for coldwave detection
- [ ] Integration with real-time weather APIs

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the API documentation at `/docs`
3. Check backend logs for error messages

---

**Built with ❤️ for Climate Resilience**
