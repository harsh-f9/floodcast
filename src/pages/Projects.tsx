import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Info, ExternalLink, ThermometerSun, Waves, CloudRain, Zap, Snowflake, Worm, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ProjectEffect } from '@/components/effects/ProjectEffect';

// Deep Ocean Blue & Sky Blue palette
const COLORS = {
  deepOcean: "#0a3d62",
  offWhite: "#eef7ff",
  white: "#ffffff",
};

interface Project {
  id: number;
  title: string;
  description: string;
  icon: React.ReactNode;
  slug: string;
  effectType?: 'heatwave' | 'flood' | 'rainfall' | 'lightning' | 'coldwave' | 'snakebite';
  comingSoon?: boolean;
  featured?: boolean;
}

interface FlippableMagneticCardProps {
  project: Project;
  magneticStrength?: number;
}

const FlippableMagneticCard = ({ project, magneticStrength = 20 }: FlippableMagneticCardProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isFlipped, setIsFlipped] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const { clientX, clientY } = e;
    if (!ref.current) return;
    const { left, top, width, height } = ref.current.getBoundingClientRect();
    const middleX = clientX - (left + width / 2);
    const middleY = clientY - (top + height / 2);
    setPosition({
      x: middleX * (magneticStrength / (width / 2)),
      y: middleY * (magneticStrength / (height / 2)),
    });
  };

  const handleMouseLeave = () => {
    setPosition({ x: 0, y: 0 });
    setIsHovered(false);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleFlip = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsFlipped(!isFlipped);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onMouseEnter={handleMouseEnter}
      animate={{ x: position.x, y: position.y }}
      transition={{ type: "spring", stiffness: 350, damping: 15, mass: 0.3 }}
      className={`w-full relative ${project.featured ? 'h-72 md:h-80' : 'h-60'}`}
      style={{ perspective: 1200 }}
    >
      <motion.div
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6, type: 'spring', stiffness: 200, damping: 20 }}
        className="w-full h-full relative"
        style={{ transformStyle: 'preserve-3d' }}
      >
        {/* Front of the Card */}
        <div
          className="absolute inset-0 shadow-md hover:shadow-2xl transition-shadow duration-300 p-4 flex flex-col justify-center items-center text-center overflow-hidden"
          style={{
            backfaceVisibility: 'hidden',
            border: project.featured ? `4px solid #f59e0b` : `3px solid ${COLORS.deepOcean}`,
            backgroundColor: 'rgba(255,255,255,0.25)',
            boxShadow: project.featured ? '0 20px 50px -12px rgba(245,158,11,0.45)' : undefined,
          }}
        >
          {/* Background Animation Effect */}
          {project.effectType && <ProjectEffect type={project.effectType} />}
          {/* Featured badge */}
          {project.featured && (
            <div className="absolute top-2 left-2 z-10 flex items-center gap-1 bg-amber-400 text-[#0a3d62] text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full shadow">
              <Sparkles size={12} />
              Flagship · Live
            </div>
          )}
          {/* Coming soon pill on front */}
          {project.comingSoon && (
            <div className="absolute top-2 left-2 z-10 bg-[#0a3d62] text-amber-300 text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full shadow">
              Coming Soon
            </div>
          )}
          {/* Top Right Utility Icons (i button and redirect link) */}
          <div className="absolute top-2 right-2 flex gap-2 z-10">
            <button
              onClick={handleFlip}
              className="p-1.5 rounded-full text-white transition-colors hover:brightness-110"
              style={{ backgroundColor: COLORS.deepOcean }}
              title="About this model"
            >
              <Info size={14} />
            </button>
            <Link
              to={project.slug}
              className="p-1.5 rounded-full text-white transition-colors hover:brightness-110 block"
              style={{ backgroundColor: COLORS.deepOcean }}
              title="Go to project page"
            >
              <ExternalLink size={14} />
            </Link>
          </div>

          <div className={`${project.featured ? 'text-5xl' : 'text-4xl'} mb-3 mt-4`}>{project.icon}</div>
          <h3
            className={`${project.featured ? 'text-lg md:text-xl' : 'text-sm md:text-sm'} font-bold uppercase tracking-tight leading-snug`}
            style={{ color: COLORS.deepOcean }}
          >
            {project.title}
          </h3>
          {project.featured && (
            <p className="text-xs font-semibold text-gray-500 mt-1">Our live flood intelligence engine</p>
          )}
        </div>

        {/* Back of the Card */}
        <div
          className="absolute inset-0 p-5 flex flex-col justify-center items-center text-center shadow-2xl"
          style={{
            backfaceVisibility: 'hidden',
            transform: 'rotateY(180deg)',
            backgroundColor: COLORS.deepOcean,
            color: COLORS.white,
            border: project.featured ? `4px solid #f59e0b` : `3px solid ${COLORS.deepOcean}`
          }}
        >
          {/* Close Info Button */}
          <button
            onClick={handleFlip}
            className="absolute top-2 right-2 p-1.5 rounded-full bg-white/20 text-white hover:bg-white/40 transition-colors z-10"
            title="Close info"
          >
            <Info size={14} />
          </button>

          {project.comingSoon && (
            <span className="bg-amber-400 text-[#0a3d62] text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full mb-3">
              Coming Soon
            </span>
          )}
          {project.featured && !project.comingSoon && (
            <span className="bg-amber-400 text-[#0a3d62] text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full mb-3">
              Flagship
            </span>
          )}
          <p className="text-white/95 text-xs font-semibold leading-relaxed overflow-y-auto max-h-full scrollbar-hide pt-1">
            {project.description}
          </p>
          {project.comingSoon && (
            <Link
              to={project.slug}
              className="mt-3 text-[11px] font-black uppercase tracking-widest bg-white/15 hover:bg-white/30 transition-colors px-3 py-1.5 rounded-full"
            >
              Play the teaser →
            </Link>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
};

export default function Projects() {
  const featured: Project = {
    id: 2,
    title: 'Floodcast',
    description: 'Our flagship live flood intelligence engine — standardized flood hazard mapping, real-time risk communication, and regional cooperation in disaster risk reduction.',
    icon: <Waves className="w-14 h-14" />,
    slug: '/projects/flood-risk',
    effectType: 'flood',
    featured: true,
  };

  const rest: Project[] = [
    {
      id: 1,
      title: 'Heatwave Prediction',
      description: 'Coordinated initiatives to monitor and predict extreme temperature events, providing critical data to support urban cooling strategies and public health interventions.',
      icon: <ThermometerSun className="w-12 h-12" />,
      slug: '/projects/heatwave-analysis',
      effectType: 'heatwave',
    },
    {
      id: 3,
      title: 'Rainfall Prediction',
      description: 'Advanced hydrological research supporting sustainable water management practices and agricultural resilience in moisture-stressed regions.',
      icon: <CloudRain className="w-12 h-12" />,
      slug: '/projects/precipitation-modeling',
      effectType: 'rainfall',
    },
    {
      id: 4,
      title: 'Lightning Prediction',
      description: 'Fostering international dialogue and technical exchange for the sustainable management of shared water resources and ecosystem services.',
      icon: <Zap className="w-12 h-12" />,
      slug: '/projects/watershed-management',
      effectType: 'lightning',
    },
    {
      id: 5,
      title: 'Coldwave Prediction',
      description: 'Comprehensive analysis of coldwave patterns and socioeconomic vulnerabilities, contributing to effective winter preparedness and social protection policies.',
      icon: <Snowflake className="w-12 h-12" />,
      slug: '/projects/coldwave-impact',
      effectType: 'coldwave',
    },
    {
      id: 6,
      title: 'Snakebite Prediction',
      description: 'Forecasting snakebite risk from monsoon, terrain and health access. The model is in training — open the page to play a Nokia-style teaser where the snake spells COMING SOON.',
      icon: <Worm className="w-12 h-12" />,
      slug: '/projects/snakebite-prediction',
      effectType: 'snakebite',
      comingSoon: true,
    },
  ];

  return (
    <div className="animate-fade-in min-h-screen" style={{ backgroundColor: COLORS.offWhite }}>
      {/* Header Section */}
      <section className="py-16 border-b border-gray-200">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="pl-6 border-l-4" style={{ borderColor: COLORS.deepOcean }}>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 uppercase" style={{ color: COLORS.deepOcean }}>
              Our Work
            </h2>
            <p className="text-lg md:text-xl text-gray-600 max-w-3xl leading-relaxed">
              Showcasing global efforts in building climate resilience through data-driven insights and international collaboration.
            </p>
          </div>
        </div>
      </section>

      {/* Featured Floodcast Section */}
      <section className="pt-12 pb-4">
        <div className="container mx-auto px-4 lg:px-8 max-w-[1600px]">
          <div className="max-w-xl mx-auto relative z-10 w-full">
            <FlippableMagneticCard project={featured} magneticStrength={15} />
          </div>
        </div>
      </section>

      {/* Remaining Projects — single row of five */}
      <section className="py-10">
        <div className="container mx-auto px-4 lg:px-8 max-w-[1600px]">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 md:gap-6">
            {rest.map((project) => (
              <div key={project.id} className="relative z-10 w-full">
                <FlippableMagneticCard project={project} magneticStrength={15} />
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
