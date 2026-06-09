import { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/atomic/card';
import { Button } from '@/components/atomic/button';
import { ChevronLeft, ChevronRight, Filter, Search, X } from 'lucide-react';
import { DotsLoader } from '../atomic/loader';

// Generic table column definition
export interface TableColumn<T> {
  key: keyof T | string;
  header: string;
  render?: (item: T, index: number) => React.ReactNode;
  sortable?: boolean;
  width?: string;
  hideable?: boolean; // Whether this column can be hidden
}

// Pagination configuration
export interface PaginationConfig {
  enabled: boolean;
  pageSize: number;
  showInfo?: boolean;
  showPageNumbers?: boolean;
}

// Table props interface
export interface GenericTableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  title?: string;
  loading?: boolean;
  error?: string | null;
  pagination?: PaginationConfig;
  totalItems?: number; // For server-side pagination
  currentPage?: number;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
  className?: string;
  tableClassName?: string;
  headerClassName?: string;
  rowClassName?: string | ((item: T, index: number) => string);
  onRowClick?: (item: T, index: number) => void;
  enableColumnFilter?: boolean; // Enable column filtering feature
  filterButtonVariant?: 'default' | 'outline' | 'ghost';
  filterButtonClassName?: string;
  searchable?: boolean;          // Show a search box that filters across the table's columns
  searchPlaceholder?: string;
  // When provided, search is SERVER-SIDE: the (debounced) query is handed back to
  // the parent (which refetches) instead of filtering the loaded rows client-side.
  onSearchChange?: (query: string) => void;
}

export function GenericTable<T extends Record<string, any>>({
  data,
  columns,
  title,
  loading = false,
  error = null,
  pagination = { enabled: false, pageSize: 10, showInfo: true, showPageNumbers: true },
  totalItems,
  currentPage: controlledCurrentPage,
  onPageChange,
  emptyMessage = "No data available",
  className = "",
  tableClassName = "",
  headerClassName = "bg-secondary",
  rowClassName = "hover:bg-gray-50",
  onRowClick,
  enableColumnFilter = false,
  filterButtonVariant = 'outline',
  filterButtonClassName = '',
  searchable = true,
  searchPlaceholder = 'Search...',
  onSearchChange,
}: GenericTableProps<T>) {
  const [internalCurrentPage, setInternalCurrentPage] = useState(1);
  const [query, setQuery] = useState('');
  const [showColumnSelector, setShowColumnSelector] = useState(false);
  const [columnVisibility, setColumnVisibility] = useState<Record<string, boolean>>(
    () => {
      const initialVisibility: Record<string, boolean> = {};
      columns.forEach(col => {
        initialVisibility[col.key.toString()] = true;
      });
      return initialVisibility;
    }
  );
  
  // Use controlled or internal pagination
  const currentPage = controlledCurrentPage || internalCurrentPage;
  const isServerSidePagination = totalItems !== undefined && onPageChange !== undefined;

  // --- Search ---
  // Server mode (onSearchChange provided): hand the debounced query to the parent
  // and render whatever it returns (no client filtering, pagination stays on).
  // Client mode: filter the loaded rows across every column's underlying value.
  const serverMode = typeof onSearchChange === 'function';
  const rawCellValue = (item: T, column: TableColumn<T>): unknown => {
    const keys = column.key.toString().split('.');
    let value: any = item;
    for (const key of keys) value = value?.[key];
    return value;
  };
  const clientSearching = searchable && !serverMode && query.trim() !== '';
  const q = query.trim().toLowerCase();
  const baseData = clientSearching
    ? data.filter(item =>
        columns.some(col => {
          const v = rawCellValue(item, col);
          return v != null && String(v).toLowerCase().includes(q);
        }))
    : data;

  // Server mode: emit ONLY on explicit submit (Search button / Enter), never
  // while typing, so each keystroke doesn't trigger a backend fetch.
  const submitServerSearch = () => {
    if (serverMode) onSearchChange?.(query.trim());
  };
  const clearSearch = () => {
    setQuery('');
    if (serverMode) onSearchChange?.('');
  };

  // Calculate pagination values (client search shows all matches, bypassing paging)
  const total = clientSearching ? baseData.length : (isServerSidePagination ? totalItems : data.length);
  const totalPages = Math.ceil(total / pagination.pageSize);
  
  // Get visible columns
  const visibleColumns = columns.filter(col => columnVisibility[col.key.toString()] ?? true);
  
  // Toggle column visibility
  const toggleColumn = (columnKey: string) => {
    setColumnVisibility(prev => ({
      ...prev,
      [columnKey]: !prev[columnKey]
    }));
  };
  
  // Get current page data (for client-side pagination)
  const getCurrentPageData = () => {
    if (clientSearching) {
      return baseData; // show all matches across the loaded rows
    }
    if (!pagination.enabled || isServerSidePagination) {
      return data;
    }
    const startIndex = (currentPage - 1) * pagination.pageSize;
    const endIndex = startIndex + pagination.pageSize;
    return data.slice(startIndex, endIndex);
  };
  
  const currentData = getCurrentPageData();
  
  // Pagination handlers
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      if (onPageChange) {
        onPageChange(page);
      } else {
        setInternalCurrentPage(page);
      }
    }
  };
  
  // Calculate display indices
  const getDisplayIndices = () => {
    if (isServerSidePagination) {
      const start = (currentPage - 1) * pagination.pageSize;
      return {
        start: start + 1,
        end: Math.min(start + pagination.pageSize, total),
      };
    } else {
      const start = pagination.enabled ? (currentPage - 1) * pagination.pageSize : 0;
      const end = pagination.enabled 
        ? Math.min(start + pagination.pageSize, total)
        : total;
      return { start: start + 1, end };
    }
  };
  
  const { start, end } = getDisplayIndices();
  
  // Render cell content
  const renderCell = (item: T, column: TableColumn<T>, index: number) => {
    if (column.render) {
      return column.render(item, index);
    }
    
    // Handle nested keys (e.g., 'user.name')
    const keys = column.key.toString().split('.');
    let value = item;
    for (const key of keys) {
      value = value?.[key];
    }
    
    return value?.toString() || '';
  };
  
  // Generate page numbers for pagination
  const getPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      const start = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
      const end = Math.min(totalPages, start + maxVisiblePages - 1);
      
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
    }
    
    return pages;
  };

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          {title && (
            <h2 className="text-3xl font-bold">
              {title}
            </h2>
          )}
        </CardHeader>
        <CardContent>
          <DotsLoader />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          {title && (
            <h2 className="text-3xl font-bold">
              {title}
            </h2>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex justify-center items-center py-8">
            <div className="text-primary-950 dark:text-primary-300">Error: {error}</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex justify-between items-center gap-3 flex-wrap">
          {title && (
            <h2 className="text-3xl font-bold">
              {title}
            </h2>
          )}

          <div className="flex items-center gap-2 ml-auto">
          {/* Search box */}
          {searchable && (
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') submitServerSearch(); }}
                  placeholder={searchPlaceholder}
                  className="pl-8 pr-8 py-2 text-sm rounded-lg border w-56
                    text-[#2d2d2d] dark:text-[#e5e5e5] bg-white dark:bg-[#2d2d2d]
                    border-[#e5e5e5] dark:border-[#444]
                    focus:outline-none focus:ring-2 focus:ring-[#bf0000]/40"
                />
                {query && (
                  <button
                    type="button"
                    onClick={clearSearch}
                    aria-label="Clear search"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              {serverMode && (
                <Button
                  variant="outline"
                  onClick={submitServerSearch}
                  className="flex items-center gap-1.5"
                >
                  <Search className="w-4 h-4" />
                  Search
                </Button>
              )}
            </div>
          )}

          {/* Column Filter Button */}
          {enableColumnFilter && (
            <div className="relative">
              <Button
                variant={filterButtonVariant}
                onClick={() => setShowColumnSelector(!showColumnSelector)}
                className={`flex items-center gap-2 ${filterButtonClassName}`}
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
                  
                  <div className="absolute right-0 mt-2 w-64 bg-card text-card-foreground rounded-lg shadow-xl border z-20 overflow-x-auto h-72">
                    <div className="p-4">
                      <h3 className="font-semibold mb-3">
                        Select Columns
                      </h3>
                      <div className="space-y-2">
                        {columns.map((column) => (
                          <label
                            key={column.key.toString()}
                            className="flex items-center gap-3 py-2 hover:bg-muted-foreground/10 rounded px-2 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={columnVisibility[column.key.toString()] ?? true}
                              onChange={() => toggleColumn(column.key.toString())}
                              className="w-4 h-4 text-red-600 rounded accent-[#bf0000] cursor-pointer"
                            />
                            <span className="text-sm">
                              {column.header}
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
          </div>
        </div>
      </CardHeader>
        
      <CardContent>
        <div className="shadow-md overflow-x-auto">
          <table className={`w-full text-left border rounded-lg ${tableClassName}`}>
            <thead className={headerClassName}>
              <tr>
                {visibleColumns.map((column, index) => (
                  <th 
                    key={index}
                    className="px-4 py-3 border-b"
                    style={{ width: column.width }}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {currentData.length === 0 ? (
                <tr>
                  <td colSpan={visibleColumns.length} className="px-4 py-8 text-center">
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                currentData.map((item, index) => {
                  const actualIndex = pagination.enabled && !isServerSidePagination 
                    ? (currentPage - 1) * pagination.pageSize + index 
                    : index;
                    
                  const rowClass = typeof rowClassName === 'function' 
                    ? rowClassName(item, actualIndex) 
                    : rowClassName;
                    
                  return (
                    <tr 
                      key={item.id || item._id || index}
                      className={`${rowClass} ${onRowClick ? 'cursor-pointer' : ''}`}
                      onClick={() => onRowClick?.(item, actualIndex)}
                    >
                      {visibleColumns.map((column, colIndex) => (
                        <td key={colIndex} className=" px-4 py-3 border-b">
                          {renderCell(item, column, actualIndex)}
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.enabled && totalPages > 1 && !clientSearching && (
          <div className="flex justify-between items-center mt-6 flex-wrap gap-4">
            {pagination.showInfo && (
              <p className="text-sm text-gray-600 dark:text-[#e5e5e5]">
                Showing {start} to {end} of {total} entries
              </p>
            )}

            <div className="flex items-center space-x-2">
              <Button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className="px-3 py-2 text-sm font-medium rounded-lg border disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1 transition-colors
                text-[#2d2d2d] dark:text-[#e5e5e5] bg-white dark:bg-[#2d2d2d] border-[#e5e5e5] dark:border-[#444]
                hover:bg-[#f8f9fa] dark:hover:bg-[#3a3a3a]"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Previous</span>
              </Button>

              {pagination.showPageNumbers && (
                <div className="flex items-center space-x-1">
                  {/* First Page */}
                  <Button
                    onClick={() => goToPage(1)}
                    className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                      currentPage === 1
                        ? 'bg-red-700 text-white border-[#bf0000]'
                        : 'bg-white text-[#2d2d2d] dark:bg-[#3b3b3b] dark:text-[#e5e5e5] border-[#e5e5e5] dark:border-[#444] hover:bg-[#f8f9fa] dark:hover:bg-[#494949]'
                    }`}
                  >
                    1
                  </Button>

                  {/* Left Ellipsis */}
                  {currentPage > 3 && (
                    <span className="px-2 text-[#2d2d2d] dark:text-[#e5e5e5]">...</span>
                  )}

                  {/* Middle Pages (3 pages max) */}
                  {(() => {
                    const pages = [];
                    let start = Math.max(2, currentPage - 1);
                    let end = Math.min(totalPages - 1, currentPage + 1);

                    // Adjust to always show 3 pages if possible
                    if (currentPage <= 2) {
                      end = Math.min(4, totalPages - 1);
                    } else if (currentPage >= totalPages - 1) {
                      start = Math.max(2, totalPages - 3);
                    }

                    for (let i = start; i <= end; i++) {
                      pages.push(
                        <Button
                          key={i}
                          onClick={() => goToPage(i)}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                            currentPage === i
                              ? 'bg-red-700 text-white border-[#bf0000]'
                              : 'bg-white text-[#2d2d2d] dark:bg-[#3b3b3b] dark:text-[#e5e5e5] border-[#e5e5e5] dark:border-[#444] hover:bg-[#f8f9fa] dark:hover:bg-[#494949]'
                          }`}
                        >
                          {i}
                        </Button>
                      );
                    }
                    return pages;
                  })()}

                  {/* Right Ellipsis */}
                  {currentPage < totalPages - 2 && (
                    <span className="px-2 text-[#2d2d2d] dark:text-[#e5e5e5]">...</span>
                  )}

                  {/* Last Page */}
                  {totalPages > 1 && (
                    <Button
                      onClick={() => goToPage(totalPages)}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                        currentPage === totalPages
                          ? 'bg-red-700 text-white border-[#bf0000]'
                          : 'bg-white text-[#2d2d2d] dark:bg-[#3b3b3b] dark:text-[#e5e5e5] border-[#e5e5e5] dark:border-[#444] hover:bg-[#f8f9fa] dark:hover:bg-[#494949]'
                      }`}
                    >
                      {totalPages}
                    </Button>
                  )}
                </div>
              )}

              <Button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="px-3 py-2 text-sm font-medium rounded-lg border disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1
                bg-[#bf0000] text-white border-[#bf0000] hover:bg-[#a00000]"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </CardContent> 
        
    </Card>
  );
}