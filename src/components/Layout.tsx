import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Home as HomeIcon } from "lucide-react";
import croLogo from "@/assets/cro-logo.jpg";

const Layout = ({ children }: { children: React.ReactNode }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  const navigation = [
    { name: "Home", path: "/" },
    { name: "Our Work", path: "/projects" },
    { name: "Team", path: "/team" },
    { name: "Insights", path: "/insights" },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-[#eef7ff] font-sans">
      {/* Top Bar */}
      <div className="text-white py-1" style={{ backgroundColor: '#0a3d62' }}>
        <div className="container mx-auto px-4 flex justify-between items-center text-[10px] md:text-sm font-light">
          <div className="flex items-center gap-2">
            <HomeIcon className="h-3 w-3" />
            <span>Welcome to the Climate Resilience Observatory</span>
          </div>
        </div>
      </div>

      {/* Main Header */}
      <header className="bg-transparent py-4 shadow-sm border-b border-gray-200">
        <div className="container mx-auto px-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <img src={croLogo} alt="CRO Logo" className="h-14 w-auto object-contain" />
            <h1 className="text-xl md:text-3xl font-bold text-gray-900 tracking-tight ml-2">
              Climate Resilience Observatory
            </h1>
          </Link>

          <div className="hidden md:flex items-center gap-6">
            <img src="/src/assets/iiitl-logo.png" alt="IIIT Lucknow" className="h-12 w-auto object-contain" />
            <img src="/src/assets/govt-up-logo.png" alt="Govt of UP" className="h-12 w-auto object-contain" />
            <img src="/src/assets/relief-commissioner-logo.jpg" alt="Relief Commissioner" className="h-12 w-auto object-contain" />
          </div>
        </div>
      </header>

      {/* Navigation Bar */}
      <nav className="sticky top-0 z-50" style={{ backgroundColor: '#1a1a2e' }}>
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between lg:justify-start w-full">
            <div className="hidden lg:flex">
              {navigation.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-6 py-3 text-sm font-semibold tracking-wide transition-colors ${isActive(item.path) ? "bg-white text-gray-900" : "text-gray-300 hover:text-white"}`}
                >
                  {item.name}
                </Link>
              ))}
            </div>

            <button
              className="lg:hidden text-white p-3 ml-auto"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X /> : <Menu />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-gray-700" style={{ backgroundColor: '#0d2137' }}>
            <div className="flex flex-col py-2">
              {navigation.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-6 py-3 ${isActive(item.path) ? "bg-white text-gray-900" : "text-white hover:bg-gray-700"}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {item.name}
                </Link>
              ))}
            </div>
          </div>
        )}
      </nav>

      {/* Main Content */}
      <main>{children}</main>

      {/* Footer */}
      <footer className="text-white mt-0" style={{ backgroundColor: '#000000' }}>
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-12">
            <div>
              <h4 className="font-bold text-lg mb-4 text-white">Climate Resilience Observatory</h4>
              <p className="text-gray-300 text-sm leading-relaxed max-w-xs">
                A joint initiative for data-driven disaster risk reduction and climate resilience analysis.
              </p>
            </div>
            <div>
              <h4 className="font-bold text-sm uppercase tracking-wider mb-4 text-white">Quick Links</h4>
              <div className="flex flex-col gap-3 text-sm text-gray-400">
                <Link to="/" className="hover:text-white transition-colors">Home</Link>
                <Link to="/projects" className="hover:text-white transition-colors">Our Work</Link>
                <Link to="/team" className="hover:text-white transition-colors">Team</Link>
              </div>
            </div>
            <div>
              <h4 className="font-bold text-sm uppercase tracking-wider mb-4 text-white">Partners</h4>
              <div className="flex flex-col gap-3 text-sm text-gray-400">
                <a href="https://iiitl.ac.in/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">IIIT Lucknow</a>
                <a href="https://rahat.up.nic.in/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">UP Relief Commissioner's Office</a>
              </div>
            </div>
          </div>
          <div className="border-t border-white/10 pt-8 text-center">
            <p className="text-gray-400 text-sm">
              © 2026 Climate Resilience Observatory — IIIT Lucknow
            </p>
          </div>
        </div>
      </footer>
    </div >
  );
};

export default Layout;
