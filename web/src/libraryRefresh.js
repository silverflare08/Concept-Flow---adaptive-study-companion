// Fetch independent sections so one unavailable endpoint cannot freeze chat history.
export async function fetchLibraryUpdates(api, fetcher) {
  const updates = {};
  const errors = [];
  await Promise.all([
    (async () => {
      try {
        const response = await fetcher(`${api}/api/courses`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
        if (!response.ok) throw new Error("Could not refresh courses.");
        const data = await response.json();
        if (!Array.isArray(data.courses)) throw new Error("Invalid course list.");
        updates.courses = data.courses;
      } catch (error) { errors.push(error.message); }
    })(),
    (async () => {
      try {
        const response = await fetcher(`${api}/api/history`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
        if (!response.ok) throw new Error("Could not refresh chat history.");
        const data = await response.json();
        if (!Array.isArray(data.conversations)) throw new Error("Invalid chat history.");
        Object.assign(updates, { conversations: data.conversations, artifacts: data.artifacts || [],
          assessments: data.assessments || [], archivedCourses: data.archived_courses || [] });
      } catch (error) { errors.push(error.message); }
    })(),
  ]);
  return { updates, error: errors.join(" ") };
}
