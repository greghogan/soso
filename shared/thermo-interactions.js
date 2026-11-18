/* Classic-script, offline reading controls. No modules, fetch, cookies or network. */
(function () {
  'use strict';
  var toggle = document.getElementById('navtoggle');
  var search = document.getElementById('lesson-search');
  var status = document.getElementById('search-status');
  function closeNav() {
    document.body.classList.remove('navopen');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }
  if (toggle) toggle.addEventListener('click', function () {
    var open = document.body.classList.toggle('navopen');
    toggle.setAttribute('aria-expanded', String(open));
  });
  function filterLessons() {
    if (!search) return;
    var query = search.value.toLowerCase().trim(), matches = 0;
    document.querySelectorAll('.sidebar .lesson-link').forEach(function (link) {
      var lesson = document.getElementById(link.hash.slice(1));
      var match = !query || (lesson && (lesson.textContent+' '+lesson.id).toLowerCase().indexOf(query) !== -1);
      link.hidden = !match;
      if (match) matches += 1;
    });
    document.querySelectorAll('.sidebar details').forEach(function (section) {
      section.hidden = !Array.from(section.querySelectorAll('a')).some(function (link) { return !link.hidden; });
      if (query) section.open = true;
    });
    if (status) status.textContent = query ? matches + ' matching lessons' : 'All lessons';
  }
  if (search) search.addEventListener('input', filterLessons);
  document.querySelectorAll('.sidebar a').forEach(function (link) { link.addEventListener('click', closeNav); });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeNav(); });
  function hideAnswers() {
    document.querySelectorAll('.self-check details, .answer-disclosure').forEach(function (item) { item.open = false; });
  }
  var hide = document.getElementById('hide-answers');
  if (hide) hide.addEventListener('click', hideAnswers);
  var reset = document.getElementById('reset-guide');
  if (reset) reset.addEventListener('click', function () {
    hideAnswers();
    document.querySelectorAll('details.sources').forEach(function (item) { item.open = false; });
    document.querySelectorAll('.sidebar details').forEach(function (item) { item.open = true; });
    if (search) { search.value = ''; filterLessons(); }
    closeNav();
  });
})();
