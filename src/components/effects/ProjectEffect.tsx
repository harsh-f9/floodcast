import { motion } from 'framer-motion';

interface ProjectEffectProps {
    type: 'heatwave' | 'flood' | 'rainfall' | 'lightning' | 'coldwave';
}

const effectData: Record<string, { src: string; isHtml: boolean }> = {
    heatwave: { src: '/heatwave.svg', isHtml: false },
    flood: { src: '/rainfall.svg', isHtml: false },
    rainfall: { src: '/rainfall.svg', isHtml: false },
    lightning: { src: '/lightning.svg', isHtml: false },
    coldwave: { src: '/coldwavesvg.svg', isHtml: false },
};

export const ProjectEffect = ({ type }: ProjectEffectProps) => {
    const data = effectData[type];

    return (
        <motion.div
            className="absolute inset-0 z-0 pointer-events-none overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
        >
            {data.isHtml ? (
                <iframe
                    src={data.src}
                    title={`${type} effect`}
                    className="w-full h-full border-0 pointer-events-none"
                    style={{ opacity: 0.75 }}
                />
            ) : (
                <img
                    src={data.src}
                    alt={`${type} effect`}
                    className="w-full h-full object-cover"
                    style={{ opacity: 0.75 }}
                />
            )}
        </motion.div>
    );
};
