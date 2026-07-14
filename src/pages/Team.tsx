import { Card } from "@/components/ui/card";
import { User } from "lucide-react";

const Team = () => {
  const teamMembers = [
    { name: "Sahil Rafaliya", role: "M.Sc. Data Science", photo: "/team-photos/sahil.png", linkedin: "https://www.linkedin.com/in/sahil-rafaliya-869210300/" },
    { name: "Srishti Garg", role: "M.Sc. Data Science", photo: "/team-photos/srishti.jpg", linkedin: "https://www.linkedin.com/in/srishti-garg-6211a81ba/" },
    { name: "Rajesh", role: "M.Sc. Data Science", photo: null, linkedin: "#" },
    { name: "Debayan Bandyopadhyay", role: "M.Sc. Data Science", photo: "/team-photos/Debayan.png", linkedin: "https://www.linkedin.com/in/debayan-bandyopadhyay-734b66247/" },
    { name: "Tarun Rai", role: "M.Sc. Data Science", photo: "/team-photos/Tarun.png", linkedin: "https://www.linkedin.com/in/tarunrai21/" },
    { name: "Gunjan", role: "M.Sc. Data Science", photo: "/team-photos/Gunjan.png", linkedin: "https://www.linkedin.com/in/gunjan-bansal-0b09a3251/" },
    { name: "Rohit Kumar Meena", role: "M.Sc. Data Science", photo: "/team-photos/Rohit.png", linkedin: "https://www.linkedin.com/in/rohit-kumar-meena-b09133380/" },
    { name: "Urmila Saini", role: "M.Sc. Data Science", photo: "/team-photos/Urmilla.png", linkedin: "https://www.linkedin.com/in/urmila-saini-271205380/" },
    { name: "Sunil Kumar", role: "M.Sc. AI & ML", photo: "/team-photos/Sunil.png", linkedin: "https://www.linkedin.com/in/sunil-kumar-ab174420a/" },
    { name: "Sridip Basu", role: "M.Sc. AI & ML", photo: "/team-photos/sridip-basu.png", linkedin: "https://www.linkedin.com/in/sridip-basu/" },
    { name: "Samir Thakur", role: "M.Sc. AI & ML", photo: "/team-photos/samir.png", linkedin: "https://www.linkedin.com/in/samir-thakur-829162381/" },
    { name: "Manas Singh", role: "M.Sc. Data Science", photo: "/team-photos/Manas.png", linkedin: "https://www.linkedin.com/in/manas-singh-5b2001357/" },
    { name: "Laxmikanta Roy", role: "M.Sc. AI & ML", photo: "/team-photos/laxmikant.png", linkedin: "https://www.linkedin.com/in/laxmikanta-roy-329a6a363/" },
    { name: "Rupsa Roy", role: "M.Sc. Data Science", photo: "/team-photos/Rupsa.png", linkedin: "https://www.linkedin.com/in/rupsa-roy-848a89380/" },
    { name: "Harsh Jain", role: "M.Sc. AI & ML", photo: "/team-photos/Harsh.png", linkedin: "https://www.linkedin.com/in/harshf9/" },
    { name: "Aishrica", role: "M.Sc. Data Science", photo: "/team-photos/Aishrica.png", linkedin: "https://www.linkedin.com/in/aishrica-dhiman-610b41294/" },
    { name: "Kamal Vasa", role: "M.Sc. AI & ML", photo: "/team-photos/Kamal.png", linkedin: "https://www.linkedin.com/in/kamalvasa/" },
    { name: "Shiva Singh", role: "M.Sc. Data Science", photo: "/team-photos/Shiva.png", linkedin: "https://www.linkedin.com/in/shiva-singh-b008aa36b/" },
    { name: "Arjun Mahesh", role: "M.Sc. AI & ML", photo: "/team-photos/Arjun.png", linkedin: "https://www.linkedin.com/in/arjun-mahesh-00a118382/" },
    { name: "Eleti Nithin Pious", role: "M.Sc. AI & ML", photo: null, linkedin: "https://www.linkedin.com/in/nithin-pious-eleti-8b240628b/" },
    { name: "Rishabh Bedi", role: "M.Sc. Data Science", photo: null, linkedin: "#" },
  ];

  const pastContributors = [
    { name: "Praveen Agarwal", role: "2022-2026", photo: "/team-photos/Praveen.jpg", linkedin: "https://www.linkedin.com/in/praveenagrawal220/" },
    { name: "Anamitra Majumder", role: "2022-2026", photo: "/team-photos/Anamitra.jpg", linkedin: "https://www.linkedin.com/in/anamitra-majumder-b59b81330/" },
    { name: "Ana Afzal", role: "2022-2026", photo: "/team-photos/Ana.jpg", linkedin: "https://www.linkedin.com/in/ana-afzal-745896281/" },
    { name: "Susanta Baidya", role: "2023-2025", photo: "/team-photos/Susanta.jpg", linkedin: "https://www.linkedin.com/in/susanta-baidya-03436628a/" },
  ];

  const MemberCard = ({
    name,
    role,
    photo,
    subRole,
    showSocials = false,
    linkedin = "#",
  }: {
    name: string;
    role: string;
    photo?: string | null;
    subRole?: string;
    showSocials?: boolean;
    linkedin?: string;
  }) => (
    <Card className="p-8 border border-gray-100 shadow-lg rounded-2xl hover:shadow-xl transition-all group flex flex-col items-center text-center bg-white">
      <div className="mb-6 relative">
        <div className="w-32 h-32 overflow-hidden rounded-full border-4 border-white shadow-md group-hover:border-un-blue transition-colors bg-gray-50 flex items-center justify-center">
          {photo ? (
            <img
              src={photo}
              alt={name}
              className="w-full h-full object-cover"
            />
          ) : (
            <User className="h-16 w-16 text-gray-300" />
          )}
        </div>
      </div>
      <h3 className="font-bold text-xl text-gray-900 mb-2 tracking-tight">{name}</h3>
      <p className="text-sm text-gray-600 font-medium leading-tight mb-1">{role}</p>
      {subRole && (
        <p className="text-sm text-gray-400 font-medium">{subRole}</p>
      )}
      {showSocials && (
        <div className="flex gap-4 mt-4">
          <a href={linkedin} target="_blank" rel="noopener noreferrer" className="hover:opacity-80 transition-opacity" title="LinkedIn">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-6 h-6 drop-shadow-sm hover:scale-110 transition-transform">
              <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" fill="#0A66C2"/>
            </svg>
          </a>
          {name === "Sridip Basu" && (
            <a href="https://orcid.org/0009-0009-4265-2959" target="_blank" rel="noopener noreferrer" className="hover:opacity-80 transition-opacity" title="ORCID">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-6 h-6 drop-shadow-sm hover:scale-110 transition-transform">
                <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zM7.369 4.378c.525 0 .947.431.947.947s-.422.949-.947.949a.95.95 0 0 1-.949-.949c0-.516.424-.947.949-.947zm-.722 3.038h1.444v10.041H6.647V7.416zm3.562 0h3.9c3.712 0 5.344 2.653 5.344 5.025 0 2.578-2.016 5.016-5.362 5.016h-3.881V7.416zm1.444 1.303v7.44h2.297c3.272 0 4.022-2.484 4.022-3.72 0-2.016-1.284-3.72-4.097-3.72h-2.222z" fill="#A6CE39"/>
              </svg>
            </a>
          )}
        </div>
      )}
    </Card>
  );

  return (
    <div className="animate-fade-in bg-gray-50/30">
      {/* Hero Section */}
      <section className="bg-un-dark-gray py-24">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl border-l-4 border-un-blue pl-8">
            <h1 className="text-5xl font-bold text-white uppercase tracking-tighter mb-4">
              Our Team
            </h1>
            <p className="text-xl text-gray-300 font-light leading-relaxed max-w-2xl">
              Meet the dedicated researchers and analysts contributing to global climate resilience and data-driven disaster risk reduction.
            </p>
          </div>
        </div>
      </section>

      {/* Team Lead Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center mb-12">
            <h2 className="text-3xl font-bold text-gray-800 uppercase tracking-widest mb-4">Team Lead</h2>
            <div className="w-20 h-1 bg-un-blue"></div>
          </div>

          <div className="flex justify-center">
            <div className="w-full max-w-sm">
              <MemberCard
                name="Dr. Deepak Kumar Singh"
                role="Ph.D (IIT Kanpur)"
                photo="/team-photos/Deepak.jpg"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Faculty Advisors Section */}
      <section className="py-20 bg-white/50">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center mb-12">
            <h2 className="text-3xl font-bold text-gray-800 uppercase tracking-widest mb-4">Faculty Advisors</h2>
            <div className="w-20 h-1 bg-un-blue"></div>
          </div>

          <div className="flex justify-center">
            <div className="w-full max-w-sm">
              <MemberCard
                name="Kumar Sindurakshit"
                role="M.Sc. Artificial Intelligence with Machine Learning"
                subRole="Queen Mary University of London"
                photo="/team-photos/Sindurakshit.jpg"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Core Contributors Grid */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center mb-16 text-center">
            <h2 className="text-3xl font-bold text-gray-800 uppercase tracking-widest mb-4">Core Contributors</h2>
            <div className="w-20 h-1 bg-un-blue"></div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
            {teamMembers.map((member, index) => (
              <MemberCard
                key={index}
                name={member.name}
                role={member.role}
                photo={member.photo}
                linkedin={member.linkedin}
                showSocials={true}
              />
            ))}
          </div>
        </div>
      </section>


      {/* Past Contributors Section */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center mb-16 text-center">
            <h2 className="text-3xl font-bold text-gray-800 uppercase tracking-widest mb-4">Past Contributors</h2>
            <div className="w-20 h-1 bg-un-blue"></div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
            {pastContributors.map((member, index) => (
              <MemberCard
                key={index}
                name={member.name}
                role={member.role}
                photo={member.photo}
                linkedin={member.linkedin}
                showSocials={true}
              />
            ))}
          </div>
        </div>
      </section>

    </div>
  );
};

export default Team;