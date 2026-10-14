export function filterLibraryItems(items, { query = "", pinnedOnly = false, courseId = null } = {}) {
  const needle = query.trim().toLocaleLowerCase();
  return items.filter(item => (!pinnedOnly || item.pinned)
    && (!courseId || item.course_id === courseId)
    && (!needle || [item.name, item.title, item.course_name].filter(Boolean).join(" ").toLocaleLowerCase().includes(needle)));
}
