// Basic drag-and-drop reassignment for tasks
window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.task-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', JSON.stringify({
        user: item.dataset.user,
        index: item.dataset.index
      }));
    });
  });

  document.querySelectorAll('.task-list').forEach(list => {
    list.addEventListener('dragover', e => e.preventDefault());
    list.addEventListener('drop', e => {
      e.preventDefault();
      const data = JSON.parse(e.dataTransfer.getData('text/plain'));
      const targetUser = list.dataset.user;
      if (!targetUser) return;
      if (data.user === targetUser) return;
      fetch('/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          task_index: data.index,
          user: data.user,
          reassign: targetUser
        })
      }).then(() => window.location.reload());
    });
  });
});
