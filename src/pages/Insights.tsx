import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import MagneticButton from "@/components/MagneticButton";

const COLORS = {
    deepOcean: "#0a3d62",
    deepOceanLight: "#1565a0",
    forestGreen: "#1b5e20",
    forestGreenAccent: "#2e7d32",
    charcoal: "#1a1a2e",
    offWhite: "#eef7ff",
};

const featuredArticle = {
    category: "AI & FLOOD PREDICTION",
    title: "How AI is Transforming Flood Prediction in Uttar Pradesh",
    description:
        "Leveraging deep learning models trained on decades of hydrological data, our research team has developed a real-time flood forecasting system that provides 72-hour advance warnings to vulnerable communities across the Ganges basin. This breakthrough technology has already been deployed in 12 districts.",
    image: "/insight-hero-flood.png",
    slug: "/insights/ai-flood-prediction",
};

const moreArticles = [
    {
        category: "EARLY WARNING SYSTEMS",
        title: "Building Next-Gen Weather Monitoring Stations Across Rural India",
        description:
            "A network of 50+ IoT-enabled stations now provides hyperlocal climate data to farmers and emergency responders in real-time.",
        image: "/insight-card-monitoring.png",
        slug: "/insights/weather-monitoring",
    },
    {
        category: "AI & CLIMATE",
        title: "Satellite Imagery Analysis for Disaster Risk Assessment",
        description:
            "Our team uses multi-spectral satellite data and machine learning to map flood-prone zones with unprecedented accuracy.",
        image: "/insight-card-ai.png",
        slug: "/insights/satellite-analysis",
    },
    {
        category: "COMMUNITY RESILIENCE",
        title: "Empowering Communities Through Disaster Preparedness Programs",
        description:
            "Training over 10,000 community volunteers across UP to respond effectively to climate emergencies and natural disasters.",
        image: "/insight-card-community.png",
        slug: "/insights/community-resilience",
    },
];

const Insights = () => {
    return (
        <div className="animate-fade-in min-h-screen" style={{ backgroundColor: COLORS.offWhite }}>
            {/* Page Header */}
            <section className="py-12 border-b border-gray-200">
                <div className="container mx-auto px-4 sm:px-8">
                    <h1 className="text-4xl md:text-5xl font-bold tracking-tight" style={{ color: COLORS.charcoal }}>
                        Insights
                    </h1>
                    <p className="mt-3 text-lg text-gray-500 max-w-2xl">
                        Research updates, field reports, and analysis from the Climate Resilience Observatory.
                    </p>
                </div>
            </section>

            {/* Featured Article — Hero Layout */}
            <section className="py-12">
                <div className="container mx-auto px-4 sm:px-8">
                    <div className="flex flex-col lg:flex-row gap-8 lg:gap-12 items-stretch">
                        {/* Left — Hero Image */}
                        <div className="lg:w-[55%]">
                            <Link to={featuredArticle.slug} className="block group overflow-hidden rounded-lg h-full">
                                <img
                                    src={featuredArticle.image}
                                    alt={featuredArticle.title}
                                    className="w-full h-full min-h-[320px] object-cover transition-transform duration-500 group-hover:scale-105"
                                />
                            </Link>
                        </div>

                        {/* Right — Featured Article Card */}
                        <div className="lg:w-[45%] flex flex-col justify-center">
                            <div className="bg-white rounded-lg border border-gray-200 p-8 lg:p-10 shadow-sm h-full flex flex-col justify-between">
                                <div>
                                    <span
                                        className="text-xs font-bold uppercase tracking-[0.15em] mb-4 inline-block"
                                        style={{ color: COLORS.deepOceanLight }}
                                    >
                                        {featuredArticle.category}
                                    </span>
                                    <h2 className="text-2xl md:text-3xl font-bold leading-snug mb-4" style={{ color: COLORS.charcoal }}>
                                        {featuredArticle.title}
                                    </h2>
                                    <p className="text-gray-600 text-base leading-relaxed">
                                        {featuredArticle.description}
                                    </p>
                                </div>
                                <Link
                                    to={featuredArticle.slug}
                                    className="mt-6 self-end inline-flex items-center gap-2 text-sm font-semibold transition-colors hover:opacity-80"
                                    style={{ color: COLORS.deepOcean }}
                                >
                                    <ArrowRight className="w-5 h-5" />
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* More News Grid */}
            <section className="pb-16">
                <div className="container mx-auto px-4 sm:px-8">
                    <h3 className="text-2xl md:text-3xl font-bold mb-8" style={{ color: COLORS.charcoal }}>
                        More News
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {moreArticles.map((article, index) => (
                            <Link
                                to={article.slug}
                                key={index}
                                className="group bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-300 flex flex-col"
                            >
                                {/* Card Text */}
                                <div className="p-6 flex-1 flex flex-col">
                                    <span
                                        className="text-[10px] font-bold uppercase tracking-[0.15em] mb-3 inline-block"
                                        style={{ color: COLORS.deepOceanLight }}
                                    >
                                        {article.category}
                                    </span>
                                    <h4 className="text-lg font-bold leading-snug mb-2" style={{ color: COLORS.charcoal }}>
                                        {article.title}
                                    </h4>
                                    <p className="text-sm text-gray-500 leading-relaxed mt-auto">
                                        {article.description}
                                    </p>
                                </div>
                                {/* Card Image */}
                                <div className="overflow-hidden">
                                    <img
                                        src={article.image}
                                        alt={article.title}
                                        className="w-full h-48 object-cover transition-transform duration-500 group-hover:scale-105"
                                    />
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>
            </section>

            {/* Director Quote Section */}
            <section className="py-16 border-t border-gray-200">
                <div className="container mx-auto px-4 sm:px-8">
                    <h3 className="text-2xl md:text-3xl font-bold mb-8" style={{ color: COLORS.charcoal }}>
                        From the Team Lead
                    </h3>

                    <Link
                        to="/insights/directors-note"
                        className="block group"
                    >
                        <div
                            className="rounded-lg p-10 lg:p-14 flex flex-col md:flex-row gap-8 items-center transition-shadow duration-300 hover:shadow-lg"
                            style={{ backgroundColor: '#e1f0fa' }}
                        >
                            <div className="flex-1">
                                <p
                                    className="text-xl md:text-2xl font-serif italic leading-relaxed mb-6"
                                    style={{ color: COLORS.charcoal }}
                                >
                                    "Climate resilience is not just about predicting the next flood — it's about building systems that
                                    empower communities to adapt, respond, and thrive in an era of unprecedented environmental change.
                                    Our work at CRO bridges the gap between cutting-edge AI research and the people who need it most."
                                </p>
                                <div className="flex items-center gap-4">
                                    <div
                                        className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg"
                                        style={{ backgroundColor: COLORS.deepOcean }}
                                    >
                                        DK
                                    </div>
                                    <div>
                                        <p className="font-bold text-base" style={{ color: COLORS.charcoal }}>
                                            Dr. Deepak Kumar Singh
                                        </p>
                                        <p className="text-sm text-gray-500">Team Lead, Climate Resilience Observatory</p>
                                    </div>
                                </div>
                            </div>

                            <div className="shrink-0">
                                <ArrowRight className="w-6 h-6 text-gray-400 group-hover:translate-x-1 transition-transform" />
                            </div>
                        </div>
                    </Link>
                </div>
            </section>

            {/* Motto Bar */}
            <section className="py-10" style={{ backgroundColor: COLORS.charcoal }}>
                <div className="container mx-auto px-4 text-center">
                    <h2 className="text-white text-2xl font-bold tracking-tighter uppercase italic">
                        Knowledge for resilience. Data for action.
                    </h2>
                </div>
            </section>
        </div>
    );
};

export default Insights;
