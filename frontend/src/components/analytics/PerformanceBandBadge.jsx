import React from 'react';

/**
 * PerformanceBandBadge — Color-coded badge for CBC grade levels.
 *
 * Props:
 *   level: 'EE' | 'ME' | 'AE' | 'BE'
 *   size: 'sm' | 'md' | 'lg' (default 'md')
 *   showLabel: Boolean (default true)
 */
const LEVEL_CONFIG = {
  EE: {
    label: 'Exceeding Expectation',
    shortLabel: 'EE',
    bgColor: 'bg-green-100',
    textColor: 'text-green-800',
    borderColor: 'border-green-200',
    dotColor: 'bg-green-500',
  },
  ME: {
    label: 'Meeting Expectation',
    shortLabel: 'ME',
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-800',
    borderColor: 'border-yellow-200',
    dotColor: 'bg-yellow-500',
  },
  AE: {
    label: 'Approaching Expectation',
    shortLabel: 'AE',
    bgColor: 'bg-orange-100',
    textColor: 'text-orange-800',
    borderColor: 'border-orange-200',
    dotColor: 'bg-orange-500',
  },
  BE: {
    label: 'Below Expectation',
    shortLabel: 'BE',
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    borderColor: 'border-red-200',
    dotColor: 'bg-red-500',
  },
};

const SIZE_CONFIG = {
  sm: {
    container: 'px-2 py-0.5 text-xs',
    dot: 'w-1.5 h-1.5',
  },
  md: {
    container: 'px-2.5 py-1 text-sm',
    dot: 'w-2 h-2',
  },
  lg: {
    container: 'px-3 py-1.5 text-base',
    dot: 'w-2.5 h-2.5',
  },
};

export default function PerformanceBandBadge({
  level,
  size = 'md',
  showLabel = true,
}) {
  const config = LEVEL_CONFIG[level] || LEVEL_CONFIG.BE;
  const sizeConfig = SIZE_CONFIG[size];

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full border font-medium
        ${config.bgColor}
        ${config.textColor}
        ${config.borderColor}
        ${sizeConfig.container}
      `}
      title={config.label}
    >
      <span className={`${config.dotColor} ${sizeConfig.dot} rounded-full`} />
      <span>{showLabel ? config.label : config.shortLabel}</span>
    </span>
  );
}