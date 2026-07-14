import { motion } from 'framer-motion';

export const HeatwaveEffect = () => {
    return (
        <motion.div
            className="absolute inset-0 z-0 pointer-events-none overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
        >
            <img
                src="/heatwave.svg"
                alt="Heatwave effect"
                className="w-full h-full object-cover opacity-40 mix-blend-multiply"
            />
        </motion.div>
    );
};
