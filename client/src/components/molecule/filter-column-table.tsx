import { Filter } from 'lucide-react';
import { Button } from '@/components/atomic/button';
import { useState } from 'react';

export interface ColumnDefinition {
  key: string;
  label: string;
}

interface FilterCustomColumnProps {
  columnDefinitions: ColumnDefinition[];
  columnVisibility: Record<string, boolean>;
  onToggleColumn: (columnKey: string) => void;
  buttonVariant?: 'default' | 'outline' | 'ghost';
  buttonClassName?: string;
}

export const FilterCustomColumn: React.FC<FilterCustomColumnProps> = ({
  columnDefinitions,
  columnVisibility,
  onToggleColumn,
  buttonVariant = 'outline',
  buttonClassName = '',
}) => {
  const [showColumnSelector, setShowColumnSelector] = useState(false);

  return (
    <div className="relative">
      <Button
        variant={buttonVariant}
        onClick={() => setShowColumnSelector(!showColumnSelector)}
        className={`flex items-center gap-2 ${buttonClassName}`}
      >
        <Filter className="w-4 h-4" />
        Customize Columns
      </Button>

      {/* Column Selector Dropdown */}
      {showColumnSelector && (
        <>
          {/* Backdrop to close dropdown when clicking outside */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowColumnSelector(false)}
          />
          
          <div className="absolute right-0 mt-2 w-64 bg-card text-card-foreground rounded-lg shadow-xl border z-20">
            <div className="p-4">
              <h3 className="font-semibold mb-3">
                Select Columns
              </h3>
              <div className="space-y-2">
                {columnDefinitions.map((column) => (
                  <label
                    key={column.key}
                    className="flex items-center gap-3 py-2 hover:bg-muted-foreground/10 rounded px-2 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={columnVisibility[column.key] ?? true}
                      onChange={() => onToggleColumn(column.key)}
                      className="w-4 h-4 text-red-600 rounded accent-[#bf0000] cursor-pointer"
                    />
                    <span className="text-sm">
                      {column.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};