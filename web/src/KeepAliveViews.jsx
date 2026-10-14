import React, { useEffect, useState } from "react";

// Navigation changes visibility, not the lifetime of an in-progress study task.
export default function KeepAliveViews({ views, active }) {
  const [visited, setVisited] = useState(() => [active]);
  useEffect(() => {
    setVisited(current => current.includes(active) ? current : [...current, active]);
  }, [active]);
  const visibleViews = visited.includes(active) ? visited : [...visited, active];
  return visibleViews.map(name => (
    <div key={name} hidden={name !== active}>
      {views[name] && React.cloneElement(views[name], { isActive: name === active })}
    </div>
  ));
}
