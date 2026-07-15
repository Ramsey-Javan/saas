import React from 'react';
import { ChevronRight, Home, Users, User, BookOpen } from 'lucide-react';

/**
 * DrillDownBreadcrumb — Navigation breadcrumb for analytics drill-down.
 *
 * Props:
 *   items: Array of { label: 'Grade 5A', icon?: 'school'|'class'|'student'|'subject', onClick?: fn }
 *   onHomeClick: Function — called when home is clicked
 */
const ICON_MAP = {
  school: Home,
  class: Users,
  student: User,
  subject: BookOpen,
};

export default function DrillDownBreadcrumb({ items = [], onHomeClick }) {
  return (
    <nav className="flex items-center gap-1 text-sm text-gray-600 flex-wrap">
      <button
        onClick={onHomeClick}
        className="flex items-center gap-1 hover:text-blue-600 transition-colors font-medium"
      >
        <Home className="w-4 h-4" />
        <span>Analytics</span>
      </button>

      {items.map((item, index) => {
        const Icon = item.icon ? ICON_MAP[item.icon] : null;
        const isLast = index === items.length - 1;

        return (
          <React.Fragment key={index}>
            <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
            {item.onClick && !isLast ? (
              <button
                onClick={item.onClick}
                className="flex items-center gap-1 hover:text-blue-600 transition-colors"
              >
                {Icon && <Icon className="w-4 h-4" />}
                <span>{item.label}</span>
              </button>
            ) : (
              <span
                className={`flex items-center gap-1 ${
                  isLast ? 'text-gray-900 font-semibold' : ''
                }`}
              >
                {Icon && <Icon className="w-4 h-4" />}
                <span>{item.label}</span>
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}