import { useNavigate, useSearch } from '@tanstack/react-router';

interface TableQueryParams {
  page?: number;
  q?: string;
}

/**
 * Keeps a table's current page + search query in the URL (?page=&q=) instead of
 * component state, so refreshing or navigating back to a paginated table lands
 * on the same page instead of silently resetting to page 1. `replace: true` so
 * paging/searching doesn't spam browser history with one entry per click.
 */
export function useTableQueryState() {
  const params = useSearch({ strict: false }) as TableQueryParams;
  const navigate = useNavigate();

  const page = params.page && params.page > 0 ? params.page : 1;
  const search = params.q ?? '';

  const setPage = (nextPage: number) => {
    navigate({
      to: '.',
      search: (prev: TableQueryParams) => ({ ...prev, page: nextPage }),
      replace: true,
    });
  };

  const setSearch = (nextSearch: string) => {
    navigate({
      to: '.',
      search: (prev: TableQueryParams) => ({
        ...prev,
        q: nextSearch || undefined,
        page: 1,
      }),
      replace: true,
    });
  };

  return { page, search, setPage, setSearch };
}
