import { Card } from "@/components/ui/card";
import { Globe } from "lucide-react";
import MagneticButton from "@/components/MagneticButton";
import UPRiskMap from "@/components/UPRiskMap";

// Deep Ocean Blue & Forest Green (darker shade) palette
const COLORS = {
  deepOcean: "#0a3d62",       // primary deep ocean blue
  deepOceanLight: "#1565a0",  // lighter accent
  forestGreen: "#1b5e20",     // dark forest green
  forestGreenAccent: "#2e7d32", // slightly lighter green accent
  charcoal: "#1a1a2e",        // dark text / backgrounds
  offWhite: "#eef7ff",        // soft sky blue bg
};

const Home = () => {

  return (
    <div className="animate-fade-in bg-[#eef7ff] min-h-screen">
      {/* Hero Section */}
      <section className="relative min-h-[600px] lg:min-h-[700px] flex items-center overflow-hidden bg-[#eef7ff]">
        {/* Full Landscape Background Image */}
        <div className="absolute inset-0 w-full h-full z-0">
          <img
            src="/landscape-hero.png"
            alt="Climate Resilience Visual"
            className="w-full h-full object-cover object-left"
          />
        </div>

        {/* Text Overlay - centered */}
        <div className="absolute inset-0 z-10 flex items-center justify-center px-4">
          <div className="w-[90%] sm:w-[70%] lg:w-[50%] max-w-2xl">
            <div
              className="flex flex-col items-center text-center backdrop-blur-[2px] p-8 lg:p-12 shadow-2xl"
              style={{
                background: 'transparent',
              }}
            >
              <h1
                className="text-[1.75rem] md:text-[2.5rem] font-bold text-white leading-[1.15] tracking-tight mb-4"
                style={{ textShadow: '0 2px 6px rgba(0,0,0,0.7), 0 0 20px rgba(10,61,98,0.4)' }}
              >
                Building Climate Resilience Through{" "}
                <span
                  className="text-[#4caf50]"
                  style={{ textShadow: '0 2px 6px rgba(0,0,0,0.7), 0 0 20px rgba(27,94,32,0.5)' }}
                >
                  Innovation & Technology
                </span>
              </h1>
              <p
                className="text-sm md:text-base text-white/90 font-semibold leading-relaxed mt-4"
                style={{ textShadow: '0 1px 4px rgba(0,0,0,0.6)' }}
              >
                A joint initiative by <span className="font-bold text-white">IIIT Lucknow</span> and the{" "}
                <span className="font-bold text-white">Office of the Relief Commissioner,</span>{" "}
                <span className="font-bold text-white">Uttar Pradesh.</span> We are leveraging artificial
                intelligence and data-driven insights to strengthen communities against climate risks.
              </p>
            </div>
          </div>
        </div>

        {/* Floating Bottom Right Buttons */}
        <div className="absolute bottom-6 right-6 lg:bottom-12 lg:right-12 flex flex-wrap gap-4 z-20">
          <MagneticButton
            onClick={() => window.location.href = '/projects'}
            className="text-white font-semibold text-xs tracking-widest px-6 py-3 uppercase shadow-lg transition-all duration-300 hover:shadow-xl hover:brightness-110"
            style={{
              background: `linear-gradient(135deg, ${COLORS.deepOcean}, ${COLORS.deepOceanLight})`,
            }}
          >
            View Projects
          </MagneticButton>
          <MagneticButton
            onClick={() => window.location.href = '/team'}
            className="text-white font-semibold text-xs tracking-widest px-6 py-3 uppercase shadow-lg transition-all duration-300 hover:shadow-xl hover:brightness-110"
            style={{
              background: `linear-gradient(135deg, ${COLORS.forestGreen}, ${COLORS.forestGreenAccent})`,
            }}
          >
            Our Team
          </MagneticButton>
        </div>
      </section>



      {/* The Initiative Detail */}
      <section className="py-20 bg-[#eef7ff]">
        <div className="container mx-auto px-4 sm:px-8">
          <div className="max-w-5xl mx-auto flex flex-col lg:flex-row gap-16 items-center">
            <div className="lg:w-1/2 space-y-8">
              <h2 className="text-3xl font-bold uppercase tracking-wide" style={{ color: COLORS.charcoal }}>
                A Joint Strategic Initiative
              </h2>
              <div className="h-1 w-20" style={{ backgroundColor: COLORS.deepOcean }} />
              <p className="text-gray-600 text-lg leading-relaxed">
                The Climate Resilience Observatory represents a landmark collaboration established to address the multi-faceted challenges of climate change. By combining rigorous academic research with practical governmental implementation, we create a feedback loop that accelerates the development of resilience strategies.
              </p>
              <p className="text-gray-600 text-lg leading-relaxed">
                Our workforce consists of leading experts in data science, meteorology, and public policy, working in unison to translate satellite imagery and sensor data into life-saving early warning systems.
              </p>
            </div>

            <div className="lg:w-1/2">
              <Card className="p-10 border-none shadow-xl rounded-none bg-white relative">
                <div className="absolute top-0 left-0 w-2 h-full" style={{ backgroundColor: COLORS.forestGreen }} />
                <h4 className="font-bold uppercase tracking-widest text-sm mb-6" style={{ color: COLORS.forestGreenAccent }}>Our Impact</h4>
                <ul className="space-y-6">
                  <li className="flex items-start gap-4">
                    <span className="text-2xl font-bold" style={{ color: COLORS.deepOcean }}>24+</span>
                    <p className="text-gray-600 text-sm italic py-1">Researchers working across international disciplines.</p>
                  </li>
                  <li className="flex items-start gap-4">
                    <span className="text-2xl font-bold" style={{ color: COLORS.deepOcean }}>100K+</span>
                    <p className="text-gray-600 text-sm italic py-1">Community members protected by early warning systems.</p>
                  </li>
                  <li className="flex items-start gap-4">
                    <span className="text-2xl font-bold" style={{ color: COLORS.deepOcean }}>5+</span>
                    <p className="text-gray-600 text-sm italic py-1">Active transboundary projects currently in operation.</p>
                  </li>
                </ul>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* CRO Insights Section */}
      <section className="border-t border-gray-200" style={{ backgroundColor: COLORS.offWhite }}>
        <div className="flex flex-col lg:flex-row h-full">
          {/* Interactive Disaster Risk Map */}
          <div className="lg:w-[60%] relative flex flex-col justify-center" style={{ backgroundColor: '#e1f0fa' }}>
            <UPRiskMap />
          </div>

          {/* Side Content */}
          <div className="lg:w-[40%] p-10 lg:p-16 flex flex-col justify-center border-l border-gray-200" style={{ backgroundColor: COLORS.offWhite }}>
            <h3 className="font-bold uppercase text-xs tracking-[0.2em] mb-6" style={{ color: COLORS.deepOcean }}>CRO Insights</h3>
            <h4 className="text-[2rem] font-bold mb-6 leading-[1.2] tracking-tight" style={{ color: COLORS.charcoal }}>
              Leading the way in Climate Action and Risk Assessment.
            </h4>
            <p className="text-gray-600 mb-8 leading-relaxed text-base">
              Our initiative leverages advanced technology to ensure that decision-makers have the insights needed to foster a resilient future for all populations.
            </p>
            <ul className="mb-10 space-y-4">
              <li className="flex items-start gap-3">
                <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ backgroundColor: COLORS.deepOcean }} />
                <span className="text-sm text-gray-600"><strong style={{ color: COLORS.charcoal }}>Risk Monitoring:</strong> Real-time hazard prediction & mitigation.</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ backgroundColor: COLORS.deepOcean }} />
                <span className="text-sm text-gray-600"><strong style={{ color: COLORS.charcoal }}>Global Reach:</strong> International collaborative frameworks.</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ backgroundColor: COLORS.deepOcean }} />
                <span className="text-sm text-gray-600"><strong style={{ color: COLORS.charcoal }}>Public Awareness:</strong> Actionable insights for local communities.</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ backgroundColor: COLORS.deepOcean }} />
                <span className="text-sm text-gray-600"><strong style={{ color: COLORS.charcoal }}>Strategic Partnerships:</strong> Bridging academia and government.</span>
              </li>
            </ul>
            <MagneticButton
              onClick={() => window.location.href = '/insights'}
              className="text-white font-bold uppercase tracking-widest text-xs px-8 py-4 self-start transition-all duration-300 hover:shadow-xl hover:brightness-110"
              style={{
                background: `linear-gradient(135deg, ${COLORS.deepOcean}, ${COLORS.forestGreen})`,
              }}
            >
              Learn More »
            </MagneticButton>
          </div>
        </div>
      </section>

      {/* Motto Bar */}
      <section className="py-12" style={{ backgroundColor: COLORS.charcoal }}>
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-white text-3xl font-bold tracking-tighter uppercase italic">Data-driven resilience for a sustainable future</h2>
        </div>
      </section>
    </div>
  );
};

export default Home;
