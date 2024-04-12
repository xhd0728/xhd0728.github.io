---
permalink: /
title: ""
excerpt: ""
author_profile: true
redirect_from: 
  - /about/
  - /about.html
---

{% if site.google_scholar_stats_use_cdn %}
{% assign gsDataBaseUrl = "https://cdn.jsdelivr.net/gh/" | append: site.repository | append: "@" %}
{% else %}
{% assign gsDataBaseUrl = "https://raw.githubusercontent.com/" | append: site.repository | append: "/" %}
{% endif %}
{% assign url_1 = gsDataBaseUrl | append: "google-scholar-stats/gs_data_shieldsio_4vrZRk0AAAAJ.json" %}
{% assign url_2 = gsDataBaseUrl | append: "google-scholar-stats/gs_data_shieldsio_B88nSvIAAAAJ.json" %}

<span class='anchor' id='about-me'></span>

{% include_relative includes/intro.md %}

{% include_relative includes/news.md %}

{% include_relative includes/publications.md %}

{% include_relative includes/awards.md %}

{% include_relative includes/projects.md %}

{% include_relative includes/educations.md %}

{% include_relative includes/talks.md %}

{% include_relative includes/internships.md %}

{% include_relative includes/connections.md %}

<p><center>
  <div id="clustrmaps-widget" style="width:50%">
    <script type='text/javascript' id='clustrmaps' src='//cdn.clustrmaps.com/map_v2.js?cl=ffffff&w=a&t=tt&d=e5X58khjwTA1_lrYnMyFF8oCJypotuYdVcB30wne0dM&co=2d78ad&cmo=3acc3a&cmn=ff5353&ct=ffffff'></script>
  </div>
</center></p>