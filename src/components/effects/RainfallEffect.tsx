import { motion } from 'framer-motion';

interface DropProps {
    delay: number;
    duration: number;
    left: number;
}

const Drop = ({ delay, duration, left }: DropProps) => (
    <motion.div
        className="absolute top-0 w-[1px] h-4 bg-sky-400/60 rounded"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: '120%', opacity: [0, 1, 1, 0] }}
        transition={{
            duration,
            repeat: Infinity,
            ease: "linear",
            delay,
        }}
        style={{ left: `${left}%` }}
    />
);

export const RainfallEffect = () => {
    // Generate an array of random drop parameters so the effect doesn't look completely uniform
    const drops = Array.from({ length: 30 }).map((_, i) => ({
        id: i,
        delay: Math.random() * 2, // Random delay between 0 and 2s
        duration: 0.6 + Math.random() * 0.4, // Random fall duration
        left: Math.random() * 100, // Random horizontal position
    }));

    return (
        <div className="absolute inset-0 overflow-hidden z-0 pointer-events-none rounded-lg bg-sky-900/10">
            {drops.map((drop) => (
                <Drop
                    key={drop.id}
                    delay={drop.delay}
                    duration={drop.duration}
                    left={drop.left}
                />
            ))}
        </div>
    );
};
