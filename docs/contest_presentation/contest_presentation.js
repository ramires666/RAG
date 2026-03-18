"use strict";

const path = require("path");
const pptxgen = require("pptxgenjs");
const {
  autoFontSize,
  imageSizingContain,
  svgToDataUri,
  safeOuterShadow,
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "OpenAI Codex";
pptx.company = "RAG Contest Deck";
pptx.subject =
  "Конкурсная презентация проекта по созданию интеллектуальной образовательной платформы";
pptx.title =
  "Создание интеллектуальной образовательной платформы для поиска, объяснения и навигации по учебным материалам";
pptx.lang = "ru-RU";
pptx.theme = {
  headFontFace: "Georgia",
  bodyFontFace: "Segoe UI",
  lang: "ru-RU",
};

const W = 13.333;
const H = 7.5;
const TOTAL_SLIDES = 12;

const COLORS = {
  navy: "0C132B",
  navy2: "111B39",
  cyan: "4BE6FF",
  cyanSoft: "B7F6FF",
  gold: "E3C58A",
  goldSoft: "F4E6C4",
  cream: "F7F1E6",
  paper: "FFF9EF",
  ink: "1A2533",
  muted: "6E7682",
  teal: "0F8E80",
  copper: "B56A4F",
  white: "FFFFFF",
  line: "D8CFBF",
  shadow: "0A0F1E",
  green: "24A074",
  greenSoft: "DCF4EA",
  peach: "F6DDD4",
};

const FONTS = {
  display: "Georgia",
  body: "Segoe UI",
  bodyStrong: "Segoe UI Semibold",
};

const ASSETS = {
  logoMark: path.join(__dirname, "logo_mark.png"),
};

function h(hex) {
  return `#${hex}`;
}

function fit(text, fontFace, opts = {}) {
  return autoFontSize(text, fontFace, {
    margin: 0,
    valign: "mid",
    breakLine: false,
    minFontSize: opts.minFontSize || 10,
    maxFontSize: opts.maxFontSize || opts.fontSize || 18,
    ...opts,
  });
}

function addFooter(slide, index, dark = false) {
  slide.addText(`${String(index).padStart(2, "0")} / ${String(TOTAL_SLIDES).padStart(2, "0")}`, {
    x: 11.9,
    y: 7.05,
    w: 0.8,
    h: 0.2,
    fontFace: FONTS.bodyStrong,
    fontSize: 9,
    color: dark ? COLORS.cyanSoft : COLORS.muted,
    align: "right",
    margin: 0,
  });
}

function addDeckLabel(slide, text, dark = false) {
  const fill = dark ? COLORS.navy2 : COLORS.white;
  const color = dark ? COLORS.cyanSoft : COLORS.teal;
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.72,
    y: 0.33,
    w: 2.3,
    h: 0.34,
    rectRadius: 0.08,
    fill: { color: fill, transparency: dark ? 8 : 0 },
    line: { color: dark ? COLORS.cyan : COLORS.line, transparency: dark ? 40 : 0, pt: 0.8 },
  });
  slide.addText(text, {
    x: 0.88,
    y: 0.4,
    w: 1.98,
    h: 0.16,
    fontFace: FONTS.bodyStrong,
    fontSize: 8.5,
    color,
    margin: 0,
    charSpace: 0.7,
    bold: true,
  });
}

function addTitle(slide, title, subtitle, dark = false, width = 7.2) {
  const titleColor = dark ? COLORS.white : COLORS.ink;
  const bodyColor = dark ? "D0D9EE" : COLORS.muted;
  slide.addText(title, {
    ...fit(title, FONTS.display, {
      x: 0.76,
      y: 0.78,
      w: width,
      h: 1.2,
      minFontSize: 24,
      maxFontSize: 31,
      bold: true,
    }),
    color: titleColor,
    bold: true,
    margin: 0,
    valign: "mid",
  });

  if (subtitle) {
    slide.addText(subtitle, {
      ...fit(subtitle, FONTS.body, {
        x: 0.82,
        y: 1.96,
        w: width - 0.1,
        h: 0.55,
        minFontSize: 11,
        maxFontSize: 15,
      }),
      color: bodyColor,
      margin: 0,
      valign: "mid",
    });
  }
}

function addDarkBackground(slide, variant = 0) {
  slide.background = { color: COLORS.navy };
  slide.addShape(pptx.ShapeType.ellipse, {
    x: -0.6,
    y: -0.45,
    w: 5.0,
    h: 3.4,
    fill: { color: variant % 2 === 0 ? COLORS.cyan : COLORS.gold, transparency: 92 },
    line: { color: variant % 2 === 0 ? COLORS.cyan : COLORS.gold, transparency: 100, pt: 0 },
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 8.8,
    y: 3.9,
    w: 4.4,
    h: 3.0,
    fill: { color: variant % 2 === 0 ? COLORS.gold : COLORS.cyan, transparency: 95 },
    line: { color: variant % 2 === 0 ? COLORS.gold : COLORS.cyan, transparency: 100, pt: 0 },
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: W,
    h: H,
    fill: { color: COLORS.navy, transparency: 6 },
    line: { color: COLORS.navy, transparency: 100, pt: 0 },
  });
  slide.addImage({
    data: svgToDataUri(
      makeConstellationSvg(1080, 720, {
        line: variant % 2 === 0 ? h(COLORS.cyan) : h(COLORS.gold),
        node: variant % 2 === 0 ? h(COLORS.cyanSoft) : h(COLORS.goldSoft),
        glow: variant % 2 === 0 ? h(COLORS.cyan) : h(COLORS.gold),
        opacity: variant % 2 === 0 ? 0.2 : 0.16,
      })
    ),
    x: 8.25,
    y: 0.2,
    w: 4.75,
    h: 6.85,
  });
}

function addLightBackground(slide, accent = COLORS.cyan) {
  slide.background = { color: COLORS.cream };
  slide.addShape(pptx.ShapeType.ellipse, {
    x: -0.6,
    y: -0.7,
    w: 3.7,
    h: 2.8,
    fill: { color: accent, transparency: 88 },
    line: { color: accent, transparency: 100, pt: 0 },
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 10.1,
    y: 4.55,
    w: 3.2,
    h: 2.3,
    fill: { color: COLORS.gold, transparency: 89 },
    line: { color: COLORS.gold, transparency: 100, pt: 0 },
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 0.35,
    y: 0.22,
    w: 12.65,
    h: 7.02,
    fill: { color: COLORS.cream, transparency: 100 },
    line: { color: COLORS.line, pt: 0.8, transparency: 15 },
  });
}

function addPill(slide, text, x, y, w, color, fill, dark = false) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h: 0.36,
    rectRadius: 0.1,
    fill: { color: fill, transparency: dark ? 8 : 0 },
    line: { color, pt: 0.8, transparency: dark ? 25 : 0 },
  });
  slide.addText(text, {
    x: x + 0.12,
    y: y + 0.085,
    w: w - 0.24,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 9,
    color,
    align: "center",
    margin: 0,
    bold: true,
  });
}

function addCard(slide, opts) {
  const {
    x,
    y,
    w,
    h,
    title,
    body,
    accent = COLORS.cyan,
    fill = COLORS.paper,
    titleColor = COLORS.ink,
    bodyColor = COLORS.muted,
    dark = false,
    titleFont = FONTS.bodyStrong,
    bodyFont = FONTS.body,
    largeTitle = false,
  } = opts;

  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.12,
    fill: { color: fill, transparency: dark ? 4 : 0 },
    line: { color: dark ? accent : COLORS.line, pt: 0.8, transparency: dark ? 30 : 0 },
    shadow: safeOuterShadow(COLORS.shadow, dark ? 0.18 : 0.12, 45, 2.5, 1.4),
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 0.2,
    y: y + 0.18,
    w: 0.55,
    h: 0.11,
    rectRadius: 0.04,
    fill: { color: accent, transparency: 0 },
    line: { color: accent, transparency: 100, pt: 0 },
  });
  slide.addText(title, {
    ...fit(title, titleFont, {
      x: x + 0.2,
      y: y + 0.34,
      w: w - 0.4,
      h: largeTitle ? 0.58 : 0.46,
      minFontSize: largeTitle ? 14 : 12,
      maxFontSize: largeTitle ? 18 : 15,
      bold: true,
    }),
    color: titleColor,
    bold: true,
    margin: 0,
  });
  slide.addText(body, {
    ...fit(body, bodyFont, {
      x: x + 0.2,
      y: y + (largeTitle ? 0.95 : 0.82),
      w: w - 0.4,
      h: h - (largeTitle ? 1.12 : 1.0),
      minFontSize: 10,
      maxFontSize: 14,
      valign: "top",
    }),
    color: bodyColor,
    margin: 0,
    valign: "top",
  });
}

function addBulletList(slide, items, x, y, w, opts = {}) {
  const color = opts.color || COLORS.ink;
  const bulletColor = opts.bulletColor || COLORS.cyan;
  const fontFace = opts.fontFace || FONTS.body;
  const fontSize = opts.fontSize || 12.6;
  const lineGap = opts.lineGap || 0.44;
  const textX = x + 0.24;
  items.forEach((item, idx) => {
    const yy = y + idx * lineGap;
    slide.addShape(pptx.ShapeType.ellipse, {
      x,
      y: yy + 0.08,
      w: 0.1,
      h: 0.1,
      fill: { color: bulletColor, transparency: 0 },
      line: { color: bulletColor, transparency: 100, pt: 0 },
    });
    slide.addText(item, {
      ...fit(item, fontFace, {
        x: textX,
        y: yy,
        w: w - 0.24,
        h: 0.28,
        minFontSize: 10,
        maxFontSize: fontSize,
      }),
      color,
      margin: 0,
    });
  });
}

function addSectionQuote(slide, text, x, y, w, dark = false) {
  const fill = dark ? COLORS.navy2 : COLORS.paper;
  const color = dark ? COLORS.white : COLORS.ink;
  const accent = dark ? COLORS.gold : COLORS.teal;
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h: 1.05,
    rectRadius: 0.14,
    fill: { color: fill, transparency: dark ? 5 : 0 },
    line: { color: accent, pt: 0.9, transparency: dark ? 28 : 0 },
  });
  slide.addText(text, {
    ...fit(text, FONTS.display, {
      x: x + 0.22,
      y: y + 0.18,
      w: w - 0.44,
      h: 0.64,
      minFontSize: 14,
      maxFontSize: 20,
      italic: true,
    }),
    color,
    italic: true,
    margin: 0,
  });
}

function addStep(slide, n, title, body, x, y, accent) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w: 2.28,
    h: 1.34,
    rectRadius: 0.14,
    fill: { color: COLORS.navy2, transparency: 2 },
    line: { color: accent, pt: 1.1, transparency: 18 },
    shadow: safeOuterShadow(COLORS.shadow, 0.16, 45, 2.2, 1.2),
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: x + 0.16,
    y: y + 0.18,
    w: 0.38,
    h: 0.38,
    fill: { color: accent, transparency: 0 },
    line: { color: accent, transparency: 100, pt: 0 },
  });
  slide.addText(String(n), {
    x: x + 0.16,
    y: y + 0.26,
    w: 0.38,
    h: 0.14,
    fontFace: FONTS.bodyStrong,
    fontSize: 11,
    color: COLORS.navy,
    align: "center",
    bold: true,
    margin: 0,
  });
  slide.addText(title, {
    ...fit(title, FONTS.bodyStrong, {
      x: x + 0.64,
      y: y + 0.15,
      w: 1.44,
      h: 0.3,
      minFontSize: 11,
      maxFontSize: 14,
      bold: true,
    }),
    color: COLORS.white,
    bold: true,
    margin: 0,
  });
  slide.addText(body, {
    ...fit(body, FONTS.body, {
      x: x + 0.18,
      y: y + 0.6,
      w: 1.92,
      h: 0.54,
      minFontSize: 9.5,
      maxFontSize: 12.2,
      valign: "top",
    }),
    color: "CDD9F6",
    margin: 0,
    valign: "top",
  });
}

function addCell(slide, text, x, y, w, h, kind = "yes") {
  const palette = {
    yes: { fill: COLORS.greenSoft, line: COLORS.green, color: COLORS.green },
    partial: { fill: COLORS.peach, line: COLORS.copper, color: COLORS.copper },
    no: { fill: "F3ECE7", line: COLORS.line, color: COLORS.muted },
  }[kind];
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.08,
    fill: { color: palette.fill, transparency: 0 },
    line: { color: palette.line, pt: 0.7, transparency: 0 },
  });
  slide.addText(text, {
    x,
    y: y + 0.1,
    w,
    h: h - 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: palette.color,
    align: "center",
    margin: 0,
    bold: true,
  });
}

function makeConstellationSvg(width, height, opts) {
  const nodes = [
    [0.18, 0.28], [0.31, 0.22], [0.47, 0.29], [0.63, 0.21], [0.79, 0.3],
    [0.24, 0.42], [0.38, 0.36], [0.54, 0.4], [0.68, 0.35], [0.82, 0.44],
    [0.16, 0.57], [0.34, 0.55], [0.5, 0.49], [0.66, 0.56], [0.79, 0.61],
    [0.28, 0.72], [0.44, 0.66], [0.58, 0.77], [0.74, 0.7], [0.54, 0.88],
  ];
  const pairs = [
    [0, 1], [0, 5], [0, 6], [1, 2], [1, 6], [2, 3], [2, 7], [2, 8], [3, 4], [3, 8],
    [4, 9], [5, 6], [5, 10], [5, 11], [6, 7], [6, 11], [6, 12], [7, 8], [7, 12], [7, 13],
    [8, 9], [8, 13], [8, 14], [9, 14], [10, 11], [11, 12], [11, 15], [12, 13], [12, 16],
    [13, 14], [13, 17], [14, 18], [15, 16], [16, 17], [17, 18], [17, 19], [12, 17], [6, 16],
    [2, 12], [3, 12], [7, 17], [11, 19], [5, 16], [1, 12],
  ];
  const lines = pairs
    .map(([a, b]) => {
      const [x1, y1] = nodes[a];
      const [x2, y2] = nodes[b];
      return `<line x1="${Math.round(x1 * width)}" y1="${Math.round(y1 * height)}" x2="${Math.round(
        x2 * width
      )}" y2="${Math.round(y2 * height)}" stroke="${opts.line}" stroke-width="3" stroke-opacity="${opts.opacity}" />`;
    })
    .join("");
  const circles = nodes
    .map(([x, y], idx) => {
      const r = idx % 4 === 0 ? 13 : 9;
      return `
        <circle cx="${Math.round(x * width)}" cy="${Math.round(y * height)}" r="${r + 5}" fill="${opts.glow}" fill-opacity="${
        opts.opacity * 0.35
      }" />
        <circle cx="${Math.round(x * width)}" cy="${Math.round(y * height)}" r="${r}" fill="${opts.node}" fill-opacity="${
        opts.opacity * 1.9 > 1 ? 1 : opts.opacity * 1.9
      }" />
      `;
    })
    .join("");
  return `
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" fill="transparent" />
    ${lines}
    ${circles}
  </svg>`;
}

function addSlideValidation(slide) {
  warnIfSlideHasOverlaps(slide, pptx);
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

function buildCover() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 0);
  addDeckLabel(slide, "КОНКУРСНАЯ ПРЕЗЕНТАЦИЯ", true);

  const title =
    "Создание интеллектуальной образовательной платформы для поиска, объяснения и навигации по учебным материалам";
  slide.addText(title, {
    ...fit(title, FONTS.display, {
      x: 0.78,
      y: 1.0,
      w: 6.85,
      h: 2.15,
      minFontSize: 26,
      maxFontSize: 33,
      bold: true,
    }),
    color: COLORS.white,
    bold: true,
    margin: 0,
    valign: "mid",
  });

  const sub =
    "Локально разворачиваемое AI-решение для института на базе семантического поиска, графа знаний и языковых моделей";
  slide.addText(sub, {
    ...fit(sub, FONTS.body, {
      x: 0.84,
      y: 3.08,
      w: 6.5,
      h: 0.7,
      minFontSize: 12,
      maxFontSize: 16,
    }),
    color: "CFDAF0",
    margin: 0,
  });

  addPill(slide, "RAG", 0.82, 4.05, 0.78, COLORS.cyan, COLORS.navy2, true);
  addPill(slide, "Knowledge Graph", 1.7, 4.05, 1.55, COLORS.gold, COLORS.navy2, true);
  addPill(slide, "On-Premise", 3.38, 4.05, 1.2, COLORS.cyanSoft, COLORS.navy2, true);
  addPill(slide, "EdTech", 4.7, 4.05, 0.92, COLORS.goldSoft, COLORS.navy2, true);

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.78,
    y: 5.0,
    w: 6.22,
    h: 1.08,
    rectRadius: 0.16,
    fill: { color: COLORS.white, transparency: 90 },
    line: { color: COLORS.cyan, pt: 1, transparency: 28 },
  });
  const coverBlurb =
    "Платформа превращает библиотеку, методические материалы и научные публикации института в единую систему знаний с понятным доступом по смыслу.";
  slide.addText(coverBlurb, {
    ...fit(coverBlurb, FONTS.bodyStrong, {
      x: 1.02,
      y: 5.28,
      w: 5.72,
      h: 0.48,
      minFontSize: 11,
      maxFontSize: 15,
      bold: true,
    }),
    color: COLORS.white,
    margin: 0,
    bold: true,
  });

  slide.addImage({
    path: ASSETS.logoMark,
    ...imageSizingContain(ASSETS.logoMark, 8.55, 0.55, 4.25, 5.75),
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 8.75,
    y: 5.48,
    w: 3.62,
    h: 0.72,
    rectRadius: 0.12,
    fill: { color: COLORS.navy2, transparency: 4 },
    line: { color: COLORS.gold, pt: 0.8, transparency: 30 },
  });
  slide.addText("Инвестиция в цифровую интеллектуальную инфраструктуру института", {
    ...fit("Инвестиция в цифровую интеллектуальную инфраструктуру института", FONTS.bodyStrong, {
      x: 9.02,
      y: 5.7,
      w: 3.08,
      h: 0.22,
      minFontSize: 9,
      maxFontSize: 11.5,
      bold: true,
    }),
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
    align: "center",
  });

  addFooter(slide, 1, true);
  addSlideValidation(slide);
}

function buildProblem() {
  const slide = pptx.addSlide();
  addLightBackground(slide, COLORS.cyan);
  addDeckLabel(slide, "ПОЧЕМУ ЭТО НУЖНО", false);
  addTitle(
    slide,
    "Сегодня знания есть в институте, но доступа к ним по смыслу почти нет",
    "Классическая цифровая библиотека хранит документы. Студенту и преподавателю нужен не архив файлов, а понятный интеллектуальный навигатор.",
    false,
    7.3
  );

  addCard(slide, {
    x: 0.82,
    y: 2.68,
    w: 2.82,
    h: 1.52,
    title: "Фрагментированные источники",
    body: "Учебники, методички, конспекты и публикации существуют раздельно и не образуют единую карту знаний.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
  });
  addCard(slide, {
    x: 3.78,
    y: 2.68,
    w: 2.82,
    h: 1.52,
    title: "Поиск по названию, а не по смыслу",
    body: "Чтобы найти нужный фрагмент, нужно помнить точный термин, автора или название файла.",
    accent: COLORS.gold,
    fill: COLORS.paper,
  });
  addCard(slide, {
    x: 0.82,
    y: 4.4,
    w: 2.82,
    h: 1.52,
    title: "Случайные источники из интернета",
    body: "Если внутри вуза нет удобного поиска, растёт зависимость от внешних и не всегда надёжных материалов.",
    accent: COLORS.copper,
    fill: COLORS.paper,
  });
  addCard(slide, {
    x: 3.78,
    y: 4.4,
    w: 2.82,
    h: 1.52,
    title: "Повторяющаяся нагрузка на преподавателей",
    body: "Одни и те же темы приходится заново объяснять разным студентам и в разных формулировках.",
    accent: COLORS.teal,
    fill: COLORS.paper,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.25,
    y: 2.6,
    w: 5.15,
    h: 3.44,
    rectRadius: 0.16,
    fill: { color: COLORS.navy, transparency: 0 },
    line: { color: COLORS.navy2, pt: 0.8, transparency: 0 },
    shadow: safeOuterShadow(COLORS.shadow, 0.16, 45, 2.3, 1.3),
  });
  slide.addText("Последствия для института", {
    x: 7.6,
    y: 2.9,
    w: 2.3,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 11.5,
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
  });
  addBulletList(
    slide,
    [
      "теряется время на поиск нужного источника;",
      "снижается глубина понимания сложных тем;",
      "ослабевает междисциплинарное мышление;",
      "не полностью раскрывается ценность библиотечного фонда;",
      "растёт рутина повторных объяснений и навигации.",
    ],
    7.56,
    3.35,
    4.25,
    {
      color: "D7E1F4",
      bulletColor: COLORS.cyan,
      fontSize: 12.2,
      lineGap: 0.49,
    }
  );

  addSectionQuote(
    slide,
    "Задача проекта: перевести работу с материалами из режима «найти файл» в режим «понять тему и получить следующий шаг».",
    7.52,
    5.58,
    4.3,
    true
  );

  addFooter(slide, 2, false);
  addSlideValidation(slide);
}

function buildSolution() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 1);
  addDeckLabel(slide, "СУТЬ РЕШЕНИЯ", true);
  addTitle(
    slide,
    "Платформа собирает разрозненные материалы в единую интеллектуальную образовательную среду",
    "Каждый документ индексируется отдельно, затем объединяется по дисциплинам и связывается общим графом знаний.",
    true,
    7.0
  );

  addStep(slide, 1, "Загрузка корпуса", "Учебники, методички, конспекты, сборники задач и статьи поступают в единый контур.", 0.86, 2.76, COLORS.cyan);
  addStep(slide, 2, "Парсинг и разметка", "Система выделяет страницы, фрагменты, темы, контекст и структуру источника.", 3.36, 2.76, COLORS.gold);
  addStep(slide, 3, "Семантический индекс", "Создаются векторные представления, карта источников и связи между фрагментами.", 5.86, 2.76, COLORS.cyan);
  addStep(slide, 4, "Граф знаний", "Понятия, термины и темы связываются между дисциплинами в единую карту.", 8.36, 2.76, COLORS.gold);
  addStep(slide, 5, "Ответ и закрепление", "Пользователь получает объяснение, источник, примеры, задачи и опцию MP3-лекции.", 10.78, 2.76, COLORS.cyan);

  for (const x of [3.02, 5.52, 8.02, 10.66]) {
    slide.addShape(pptx.ShapeType.line, {
      x,
      y: 3.43,
      w: 0.28,
      h: 0,
      line: { color: COLORS.cyanSoft, pt: 1.1, transparency: 28, beginArrowType: "none", endArrowType: "triangle" },
    });
  }

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.86,
    y: 4.62,
    w: 5.9,
    h: 1.84,
    rectRadius: 0.16,
    fill: { color: COLORS.white, transparency: 92 },
    line: { color: COLORS.cyan, pt: 0.9, transparency: 26 },
  });
  slide.addText("Пример запроса студента", {
    x: 1.14,
    y: 4.88,
    w: 2.1,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
  });
  const query = "«Объясни интеграл простыми словами и дай задачи на закрепление»";
  slide.addText(query, {
    ...fit(query, FONTS.display, {
      x: 1.14,
      y: 5.22,
      w: 5.18,
      h: 0.58,
      minFontSize: 14,
      maxFontSize: 19,
      italic: true,
    }),
    color: COLORS.white,
    italic: true,
    margin: 0,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.24,
    y: 4.48,
    w: 4.95,
    h: 1.98,
    rectRadius: 0.16,
    fill: { color: COLORS.paper, transparency: 0 },
    line: { color: COLORS.line, pt: 0.8, transparency: 0 },
    shadow: safeOuterShadow(COLORS.shadow, 0.15, 45, 2.2, 1.2),
  });
  slide.addText("Что получает пользователь", {
    x: 7.5,
    y: 4.76,
    w: 2.3,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.teal,
    margin: 0,
    bold: true,
  });
  addBulletList(
    slide,
    [
      "понятное объяснение темы;",
      "реальные источники и страницы;",
      "межпредметные аналогии;",
      "вопросы и задачи на закрепление;",
      "персонализированную MP3-лекцию.",
    ],
    7.48,
    5.08,
    4.0,
    {
      color: COLORS.ink,
      bulletColor: COLORS.cyan,
      fontSize: 11.8,
      lineGap: 0.3,
    }
  );

  addFooter(slide, 3, true);
  addSlideValidation(slide);
}

function buildStudents() {
  const slide = pptx.addSlide();
  addLightBackground(slide, COLORS.gold);
  addDeckLabel(slide, "ЦЕННОСТЬ ДЛЯ СТУДЕНТОВ", false);
  addTitle(
    slide,
    "Платформа становится для студента персональным навигатором по знаниям, а не просто поиском по файлам",
    "Поддерживает подготовку к семинару, экзамену, курсовой работе и самостоятельному повторению материала.",
    false,
    7.55
  );

  addCard(slide, {
    x: 0.84,
    y: 2.56,
    w: 2.78,
    h: 1.54,
    title: "Найти по смыслу",
    body: "Можно искать даже по неполному описанию темы, формулы, примера или ассоциации.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 3.78,
    y: 2.56,
    w: 2.78,
    h: 1.54,
    title: "Понять простым языком",
    body: "Система объясняет сложные темы доступно, но с опорой на утверждённые источники института.",
    accent: COLORS.teal,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 0.84,
    y: 4.3,
    w: 2.78,
    h: 1.54,
    title: "Закрепить задачами",
    body: "После объяснения можно сразу получить упражнения, вопросы и траекторию следующего шага.",
    accent: COLORS.copper,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 3.78,
    y: 4.3,
    w: 2.78,
    h: 1.54,
    title: "Учиться на ходу",
    body: "Персонализированные аудиолекции позволяют повторять тему вне аудитории и в удобном темпе.",
    accent: COLORS.gold,
    fill: COLORS.paper,
    largeTitle: true,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.18,
    y: 2.52,
    w: 5.18,
    h: 3.42,
    rectRadius: 0.16,
    fill: { color: COLORS.navy, transparency: 0 },
    line: { color: COLORS.navy, pt: 0.8, transparency: 0 },
  });
  slide.addText("Ключевые сценарии использования", {
    x: 7.5,
    y: 2.84,
    w: 2.55,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
  });
  addBulletList(
    slide,
    [
      "подготовка к семинару и экзамену;",
      "понимание сложной абстракции через аналогию;",
      "поиск нужного учебника без точного названия;",
      "подбор материалов для курсовой и диплома;",
      "диагностика пробелов и повторение темы.",
    ],
    7.44,
    3.18,
    4.18,
    {
      color: "D6E2F5",
      bulletColor: COLORS.cyan,
      fontSize: 12.3,
      lineGap: 0.46,
    }
  );

  addSectionQuote(
    slide,
    "Для студента это 24/7 помощник, который не заменяет преподавателя, а усиливает самостоятельную работу.",
    7.42,
    5.5,
    4.32,
    true
  );

  addFooter(slide, 4, false);
  addSlideValidation(slide);
}

function buildInstitute() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 2);
  addDeckLabel(slide, "ЦЕННОСТЬ ДЛЯ ИНСТИТУТА", true);
  addTitle(
    slide,
    "Проект усиливает уже существующие ресурсы института и превращает их в конкурентное преимущество",
    "Это не очередной чат-бот, а базовый слой интеллектуальной образовательной инфраструктуры.",
    true,
    7.3
  );

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.86,
    y: 2.6,
    w: 5.56,
    h: 3.42,
    rectRadius: 0.18,
    fill: { color: COLORS.white, transparency: 92 },
    line: { color: COLORS.gold, pt: 0.9, transparency: 28 },
  });
  slide.addText("Эффект для института", {
    x: 1.14,
    y: 2.9,
    w: 1.95,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
  });
  addBulletList(
    slide,
    [
      "растёт фактическая полезность библиотечного и методического фонда;",
      "сокращается время поиска материалов и типовых объяснений;",
      "появляется управляемая единая среда учебных и научных знаний;",
      "усиливается репутация института как площадки реальной цифровой трансформации;",
      "создаётся масштабируемая база для будущих сервисов кафедр и лабораторий.",
    ],
    1.1,
    3.24,
    4.84,
    {
      color: COLORS.white,
      bulletColor: COLORS.cyan,
      fontSize: 12.2,
      lineGap: 0.46,
    }
  );

  addCard(slide, {
    x: 6.82,
    y: 2.58,
    w: 2.7,
    h: 1.42,
    title: "Для преподавателей",
    body: "Быстрый доступ к материалам, примерам, задачам и опора на единый корпус источников.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 9.7,
    y: 2.58,
    w: 2.7,
    h: 1.42,
    title: "Для библиотеки и УМУ",
    body: "Интеллектуальная надстройка над каталогами и фондами вместо пассивного хранения PDF.",
    accent: COLORS.gold,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 6.82,
    y: 4.18,
    w: 2.7,
    h: 1.42,
    title: "Для безопасности",
    body: "Локальное развёртывание позволяет не передавать чувствительные материалы во внешние сервисы.",
    accent: COLORS.teal,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 9.7,
    y: 4.18,
    w: 2.7,
    h: 1.42,
    title: "Для стратегии развития",
    body: "Пилот можно расширить от нескольких дисциплин до общеинститутской платформы без смены концепции.",
    accent: COLORS.copper,
    fill: COLORS.paper,
    largeTitle: true,
  });

  addFooter(slide, 5, true);
  addSlideValidation(slide);
}

function buildInnovation() {
  const slide = pptx.addSlide();
  addLightBackground(slide, COLORS.cyan);
  addDeckLabel(slide, "ТЕХНОЛОГИЧНОСТЬ И НОВИЗНА", false);
  addTitle(
    slide,
    "Проект соответствует технологическим приоритетам и соединяет несколько критических технологий в одну систему",
    "Главная инновация в том, что поиск, объяснение, межпредметные связи, практика и аудиолекции работают в едином образовательном контуре.",
    false,
    7.6
  );

  slide.addText("Технологический стек проекта", {
    x: 0.86,
    y: 2.56,
    w: 2.28,
    h: 0.2,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.teal,
    margin: 0,
    bold: true,
  });
  addPill(slide, "Семантический поиск по документам", 0.86, 2.92, 2.86, COLORS.cyan, COLORS.paper);
  addPill(slide, "RAG с опорой на источники", 0.86, 3.4, 2.6, COLORS.teal, COLORS.paper);
  addPill(slide, "Граф знаний и межпредметные связи", 0.86, 3.88, 3.1, COLORS.gold, COLORS.paper);
  addPill(slide, "Локальные / институциональные LLM", 0.86, 4.36, 3.14, COLORS.copper, COLORS.paper);
  addPill(slide, "TTS и аудиоформат MP3", 0.86, 4.84, 2.26, COLORS.teal, COLORS.paper);

  slide.addShape(pptx.ShapeType.ellipse, {
    x: 7.18,
    y: 2.44,
    w: 3.65,
    h: 3.65,
    fill: { color: COLORS.navy, transparency: 0 },
    line: { color: COLORS.cyan, pt: 1.2, transparency: 15 },
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 7.88,
    y: 3.14,
    w: 2.25,
    h: 2.25,
    fill: { color: COLORS.navy2, transparency: 0 },
    line: { color: COLORS.gold, pt: 1.1, transparency: 12 },
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 8.58,
    y: 3.84,
    w: 0.86,
    h: 0.86,
    fill: { color: COLORS.cyan, transparency: 0 },
    line: { color: COLORS.cyan, transparency: 100, pt: 0 },
  });

  slide.addText("Образовательный контур", {
    x: 7.68,
    y: 2.98,
    w: 2.62,
    h: 0.22,
    fontFace: FONTS.bodyStrong,
    fontSize: 12,
    color: COLORS.white,
    align: "center",
    margin: 0,
    bold: true,
  });
  slide.addText("RAG + граф знаний + маршрутизация", {
    x: 8.05,
    y: 3.8,
    w: 1.9,
    h: 0.26,
    fontFace: FONTS.bodyStrong,
    fontSize: 10,
    color: COLORS.goldSoft,
    align: "center",
    margin: 0,
    bold: true,
  });
  slide.addText("источники", {
    x: 8.62,
    y: 4.12,
    w: 0.78,
    h: 0.14,
    fontFace: FONTS.bodyStrong,
    fontSize: 8.5,
    color: COLORS.navy,
    align: "center",
    margin: 0,
    bold: true,
  });

  addCard(slide, {
    x: 10.66,
    y: 2.68,
    w: 1.94,
    h: 1.2,
    title: "Не чат-бот",
    body: "Система отвечает по документам института, а не по абстрактной памяти модели.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 10.66,
    y: 4.04,
    w: 1.94,
    h: 1.2,
    title: "Не каталог",
    body: "Платформа связывает дисциплины и превращает корпус PDF в рабочую карту знаний.",
    accent: COLORS.gold,
    fill: COLORS.paper,
    largeTitle: true,
  });

  addFooter(slide, 6, false);
  addSlideValidation(slide);
}

function buildReadiness() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 3);
  addDeckLabel(slide, "ЗАДЕЛ УЖЕ СОЗДАН", true);
  addTitle(
    slide,
    "Ключевой MVP-контур уже реализован в рабочей кодовой базе",
    "Это повышает достижимость проекта: концепция подтверждена не только идеей, но и реальными модулями, API и пользовательским интерфейсом.",
    true,
    7.24
  );

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.84,
    y: 2.58,
    w: 6.28,
    h: 3.96,
    rectRadius: 0.16,
    fill: { color: COLORS.paper, transparency: 0 },
    line: { color: COLORS.line, pt: 0.8, transparency: 0 },
    shadow: safeOuterShadow(COLORS.shadow, 0.16, 45, 2.3, 1.3),
  });
  slide.addText("Реализованные модули MVP", {
    x: 1.1,
    y: 2.86,
    w: 2.55,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.teal,
    margin: 0,
    bold: true,
  });

  const modules = [
    ["PDF upload", COLORS.cyan],
    ["Parser & catalog", COLORS.gold],
    ["LightRAG indexing", COLORS.teal],
    ["Query router", COLORS.copper],
    ["Reindex / repair jobs", COLORS.cyan],
    ["Web UI + API", COLORS.gold],
  ];
  modules.forEach(([label, accent], idx) => {
    const row = Math.floor(idx / 2);
    const col = idx % 2;
    addPill(slide, label, 1.1 + col * 2.8, 3.26 + row * 0.74, 2.48, accent, COLORS.cream);
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 1.12,
    y: 5.62,
    w: 5.7,
    h: 0.56,
    rectRadius: 0.08,
    fill: { color: COLORS.navy, transparency: 0 },
    line: { color: COLORS.navy, transparency: 100, pt: 0 },
  });
  const apiText = "API уже покрывает базовый цикл: /books/upload • /books/{id}/index • /ask";
  slide.addText(apiText, {
    ...fit(apiText, FONTS.bodyStrong, {
      x: 1.34,
      y: 5.8,
      w: 5.24,
      h: 0.16,
      minFontSize: 9.5,
      maxFontSize: 11.5,
      bold: true,
    }),
    color: COLORS.goldSoft,
    bold: true,
    align: "center",
    margin: 0,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.44,
    y: 2.58,
    w: 4.8,
    h: 3.96,
    rectRadius: 0.18,
    fill: { color: COLORS.white, transparency: 94 },
    line: { color: COLORS.cyan, pt: 0.9, transparency: 28 },
  });
  slide.addText("Эскиз пользовательского контура", {
    x: 7.72,
    y: 2.84,
    w: 2.7,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.goldSoft,
    margin: 0,
    bold: true,
  });

  drawMockUi(slide, 7.72, 3.16, 4.24, 2.96);

  addFooter(slide, 7, true);
  addSlideValidation(slide);
}

function buildComparison() {
  const slide = pptx.addSlide();
  addLightBackground(slide, COLORS.cyan);
  addDeckLabel(slide, "КОНКУРЕНТНЫЕ ПРЕИМУЩЕСТВА", false);
  addTitle(
    slide,
    "Преимущество проекта в том, что он соединяет сильные стороны поиска, обучения и локального внедрения",
    "Сравнение показывает, что ни электронная библиотека, ни обычный чат-бот не закрывают полный образовательный контур.",
    false,
    7.72
  );

  const startX = 0.86;
  const startY = 2.68;
  const rowH = 0.48;
  const labelW = 3.92;
  const colW = 2.18;
  const gap = 0.2;

  slide.addText("Критерий", {
    x: startX + 0.12,
    y: startY - 0.38,
    w: labelW - 0.24,
    h: 0.18,
    fontFace: FONTS.bodyStrong,
    fontSize: 10.5,
    color: COLORS.teal,
    margin: 0,
    bold: true,
  });
  ["Электронная библиотека", "Обычный чат-бот", "Предлагаемая платформа"].forEach((label, idx) => {
    slide.addText(label, {
      ...fit(label, FONTS.bodyStrong, {
        x: startX + labelW + idx * (colW + gap),
        y: startY - 0.44,
        w: colW,
        h: 0.3,
        minFontSize: 9.5,
        maxFontSize: 11.5,
        bold: true,
      }),
      color: COLORS.ink,
      bold: true,
      align: "center",
      margin: 0,
    });
  });

  const rows = [
    ["Работает по документам института", "yes", "partial", "yes"],
    ["Показывает реальные источники и страницы", "partial", "partial", "yes"],
    ["Ищет по смыслу, а не только по ключевому слову", "no", "partial", "yes"],
    ["Строит межпредметные связи", "no", "partial", "yes"],
    ["Подбирает задачи и следующий шаг", "no", "partial", "yes"],
    ["Можно развернуть локально внутри вуза", "partial", "partial", "yes"],
  ];

  rows.forEach((row, idx) => {
    const y = startY + idx * (rowH + 0.10);
    slide.addShape(pptx.ShapeType.roundRect, {
      x: startX,
      y,
      w: labelW,
      h: rowH,
      rectRadius: 0.08,
      fill: { color: idx % 2 === 0 ? COLORS.paper : "FBF6EE", transparency: 0 },
      line: { color: COLORS.line, pt: 0.6, transparency: 0 },
    });
    slide.addText(row[0], {
      ...fit(row[0], FONTS.body, {
        x: startX + 0.16,
        y: y + 0.11,
        w: labelW - 0.32,
        h: rowH - 0.18,
        minFontSize: 10,
        maxFontSize: 12.5,
      }),
      color: COLORS.ink,
      margin: 0,
    });
    addCell(slide, cellLabel(row[1]), startX + labelW, y, colW, rowH, row[1]);
    addCell(slide, cellLabel(row[2]), startX + labelW + colW + gap, y, colW, rowH, row[2]);
    addCell(slide, cellLabel(row[3]), startX + labelW + 2 * (colW + gap), y, colW, rowH, row[3]);
  });

  addSectionQuote(
    slide,
    "Платформа выигрывает там, где важны точность источников, локальное развёртывание и реальное сопровождение учебного процесса.",
    0.86,
    6.20,
    11.2,
    false
  );

  addFooter(slide, 8, false);
  addSlideValidation(slide);
}

function buildMarket() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 4);
  addDeckLabel(slide, "РЫНОК И МАСШТАБИРОВАНИЕ", true);
  addTitle(
    slide,
    "У проекта есть понятный пилотный сегмент и реалистичный путь коммерческой реализации",
    "Первый заказчик и главный бенефициар может находиться внутри института, а затем решение масштабируется на другие образовательные организации.",
    true,
    7.42
  );

  addCard(slide, {
    x: 0.84,
    y: 2.6,
    w: 3.34,
    h: 1.22,
    title: "Студенты и магистранты",
    body: "Основные пользователи для учёбы, экзаменов, курсовых и научной подготовки.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
  });
  addCard(slide, {
    x: 0.84,
    y: 4.04,
    w: 3.34,
    h: 1.22,
    title: "Преподаватели и библиотеки",
    body: "Внутренние заказчики пилота: кафедры, преподаватели, библиотеки и УМУ.",
    accent: COLORS.gold,
    fill: COLORS.paper,
  });
  addCard(slide, {
    x: 0.84,
    y: 5.48,
    w: 3.34,
    h: 1.22,
    title: "Исследовательские группы",
    body: "Следующий сегмент роста: публикации, обзор литературы и межтематические связи.",
    accent: COLORS.teal,
    fill: COLORS.paper,
  });

  const steps = [
    ["1", "Пилот", "2-3 дисциплины внутри института", 4.62, 5.2, COLORS.cyan],
    ["2", "Расширение", "кафедры, библиотека, общеинститутский контур", 7.04, 4.38, COLORS.gold],
    ["3", "Тиражирование", "другие вузы, колледжи, корпоративные учебные центры", 9.54, 3.54, COLORS.cyan],
  ];
  steps.forEach(([n, title, body, x, y, accent]) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x,
      y,
      w: 2.54,
      h: 1.34,
      rectRadius: 0.14,
      fill: { color: COLORS.paper, transparency: 0 },
      line: { color: accent, pt: 1, transparency: 0 },
      shadow: safeOuterShadow(COLORS.shadow, 0.16, 45, 2.2, 1.2),
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: x + 0.16,
      y: y + 0.17,
      w: 0.38,
      h: 0.38,
      fill: { color: accent, transparency: 0 },
      line: { color: accent, transparency: 100, pt: 0 },
    });
    slide.addText(n, {
      x: x + 0.16,
      y: y + 0.26,
      w: 0.38,
      h: 0.12,
      fontFace: FONTS.bodyStrong,
      fontSize: 10.5,
      color: COLORS.navy,
      align: "center",
      margin: 0,
      bold: true,
    });
    slide.addText(title, {
      x: x + 0.64,
      y: y + 0.16,
      w: 1.62,
      h: 0.16,
      fontFace: FONTS.bodyStrong,
      fontSize: 12,
      color: COLORS.ink,
      margin: 0,
      bold: true,
    });
    slide.addText(body, {
      ...fit(body, FONTS.body, {
        x: x + 0.18,
        y: y + 0.56,
        w: 2.12,
        h: 0.5,
        minFontSize: 9.5,
        maxFontSize: 11.8,
      }),
      color: COLORS.muted,
      margin: 0,
    });
  });

  addPill(slide, "On-premise лицензия", 4.62, 6.18, 1.88, COLORS.cyanSoft, COLORS.navy2, true);
  addPill(slide, "интеграция и настройка", 6.62, 6.18, 2.02, COLORS.goldSoft, COLORS.navy2, true);
  addPill(slide, "техническое сопровождение", 8.78, 6.18, 2.1, COLORS.cyanSoft, COLORS.navy2, true);
  addPill(slide, "дисциплинарные модули", 11.02, 6.18, 1.54, COLORS.goldSoft, COLORS.navy2, true);

  addFooter(slide, 9, true);
  addSlideValidation(slide);
}

function drawMockUi(slide, x, y, w, h) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.12,
    fill: { color: COLORS.cream, transparency: 0 },
    line: { color: COLORS.line, pt: 0.8, transparency: 0 },
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 0.14,
    y: y + 0.16,
    w: 1.28,
    h: h - 0.32,
    rectRadius: 0.1,
    fill: { color: "F5ECDD", transparency: 0 },
    line: { color: COLORS.line, pt: 0.6, transparency: 0 },
  });
  slide.addText("Библиотека", {
    x: x + 0.28,
    y: y + 0.34,
    w: 0.86,
    h: 0.14,
    fontFace: FONTS.bodyStrong,
    fontSize: 9.2,
    color: COLORS.teal,
    margin: 0,
    bold: true,
  });

  const chips = [
    ["Математика", COLORS.cyan],
    ["Физика", COLORS.gold],
    ["Информатика", COLORS.teal],
  ];
  chips.forEach(([label, color], idx) => {
    addPill(slide, label, x + 0.28, y + 0.68 + idx * 0.48, 0.92, color, COLORS.paper);
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 1.58,
    y: y + 0.16,
    w: w - 1.72,
    h: 0.52,
    rectRadius: 0.1,
    fill: { color: COLORS.white, transparency: 0 },
    line: { color: COLORS.line, pt: 0.6, transparency: 0 },
  });
  slide.addText("Объясни интеграл простыми словами", {
    x: x + 1.82,
    y: y + 0.34,
    w: 2.1,
    h: 0.14,
    fontFace: FONTS.body,
    fontSize: 9.2,
    color: COLORS.muted,
    margin: 0,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 1.58,
    y: y + 0.9,
    w: w - 1.72,
    h: 1.12,
    rectRadius: 0.1,
    fill: { color: COLORS.white, transparency: 0 },
    line: { color: COLORS.line, pt: 0.6, transparency: 0 },
  });
  slide.addText("Краткое объяснение", {
    x: x + 1.82,
    y: y + 1.1,
    w: 1.32,
    h: 0.16,
    fontFace: FONTS.bodyStrong,
    fontSize: 9.3,
    color: COLORS.ink,
    margin: 0,
    bold: true,
  });
  const explain =
    "Интеграл позволяет оценить суммарный эффект бесконечно малого изменения и увидеть общую величину из множества малых частей.";
  slide.addText(explain, {
    ...fit(explain, FONTS.body, {
      x: x + 1.82,
      y: y + 1.34,
      w: 2.28,
      h: 0.46,
      minFontSize: 8.8,
      maxFontSize: 10.4,
    }),
    color: COLORS.muted,
    margin: 0,
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 1.58,
    y: y + 2.18,
    w: 1.52,
    h: 0.54,
    rectRadius: 0.1,
    fill: { color: COLORS.greenSoft, transparency: 0 },
    line: { color: COLORS.green, pt: 0.6, transparency: 0 },
  });
  slide.addText("Источник: стр. 184", {
    x: x + 1.7,
    y: y + 2.36,
    w: 1.24,
    h: 0.12,
    fontFace: FONTS.bodyStrong,
    fontSize: 8.8,
    color: COLORS.green,
    margin: 0,
    bold: true,
    align: "center",
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: x + 3.24,
    y: y + 2.18,
    w: 1.52,
    h: 0.54,
    rectRadius: 0.1,
    fill: { color: COLORS.peach, transparency: 0 },
    line: { color: COLORS.copper, pt: 0.6, transparency: 0 },
  });
  slide.addText("Задачи на закрепление", {
    x: x + 3.34,
    y: y + 2.36,
    w: 1.3,
    h: 0.12,
    fontFace: FONTS.bodyStrong,
    fontSize: 8.5,
    color: COLORS.copper,
    margin: 0,
    bold: true,
    align: "center",
  });
}

function buildRoadmap() {
  const slide = pptx.addSlide();
  addLightBackground(slide, COLORS.gold);
  addDeckLabel(slide, "ДОСТИЖИМОСТЬ И КОНТРОЛЬ РЕЗУЛЬТАТА", false);
  addTitle(
    slide,
    "Проект можно внедрять поэтапно, начиная с ограниченного пилота и быстро измеряя эффект",
    "Архитектура позволяет не ждать полного масштаба: первый полезный результат появляется уже на пилотном контуре.",
    false,
    7.7
  );

  const points = [
    ["1", "Корпус материалов"],
    ["2", "Пилотная версия"],
    ["3", "Межпредметный слой"],
    ["4", "Задачи и рекомендации"],
    ["5", "Научный контур"],
    ["6", "Интеграция в среду института"],
  ];

  slide.addShape(pptx.ShapeType.line, {
    x: 1.0,
    y: 3.1,
    w: 11.05,
    h: 0,
    line: { color: COLORS.line, pt: 1.4, transparency: 0 },
  });
  points.forEach(([n, label], idx) => {
    const x = 1.0 + idx * 2.18;
    slide.addShape(pptx.ShapeType.ellipse, {
      x,
      y: 2.84,
      w: 0.52,
      h: 0.52,
      fill: { color: idx % 2 === 0 ? COLORS.cyan : COLORS.gold, transparency: 0 },
      line: { color: idx % 2 === 0 ? COLORS.cyan : COLORS.gold, transparency: 100, pt: 0 },
    });
    slide.addText(n, {
      x,
      y: 2.98,
      w: 0.52,
      h: 0.12,
      fontFace: FONTS.bodyStrong,
      fontSize: 10,
      color: COLORS.navy,
      align: "center",
      margin: 0,
      bold: true,
    });
    slide.addText(label, {
      ...fit(label, FONTS.bodyStrong, {
        x: x - 0.35,
        y: 3.48,
        w: 1.24,
        h: 0.44,
        minFontSize: 9.2,
        maxFontSize: 11.4,
        bold: true,
      }),
      color: COLORS.ink,
      align: "center",
      margin: 0,
      bold: true,
    });
  });

  addCard(slide, {
    x: 0.86,
    y: 4.5,
    w: 4.02,
    h: 1.64,
    title: "Ключевые метрики успеха",
    body: "время поиска нужной темы;\nточность релевантного источника;\nудовлетворённость студентов и преподавателей;\nчисло проиндексированных материалов и полезных ответов.",
    accent: COLORS.teal,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 5.06,
    y: 4.5,
    w: 3.34,
    h: 1.64,
    title: "Снижение рисков",
    body: "опора на источники вместо свободной генерации;\nпарсинг, нормализация и OCR;\nмногоуровневая архитектура поиска.",
    accent: COLORS.copper,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 8.58,
    y: 4.5,
    w: 3.66,
    h: 1.64,
    title: "Доверие и безопасность",
    body: "локальное развёртывание внутри института позволяет контролировать материалы, качество ответов и конфиденциальность.",
    accent: COLORS.gold,
    fill: COLORS.paper,
    largeTitle: true,
  });

  addFooter(slide, 10, false);
  addSlideValidation(slide);
}

function buildTeam() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 5);
  addDeckLabel(slide, "КОМАНДА И РЕАЛИЗУЕМОСТЬ", true);
  addTitle(
    slide,
    "Команда закрывает ключевые компетенции: управление, архитектуру, ML, UX и контроль качества",
    "Это снижает риск недореализации и делает переход от концепции к пилоту практически достижимым.",
    true,
    7.54
  );

  const teamCards = [
    [0.84, "Технический руководитель", "архитектура платформы, интеграция модулей и техническое качество реализации", COLORS.cyan],
    [3.32, "Руководитель проекта", "сроки, координация работ, пилот и взаимодействие с институтом", COLORS.gold],
    [5.8, "ML-инженер", "языковые модели, индексация документов, граф знаний и валидация качества ответов", COLORS.teal],
    [8.28, "Художник-дизайнер", "визуальная концепция, удобство интерфейса и понятность пользовательского опыта", COLORS.copper],
    [10.76, "QA / тестирование", "проверка сценариев, устойчивости системы и качества пользовательского контура", COLORS.cyan],
  ];

  teamCards.forEach(([x, title, body, accent]) => {
    addCard(slide, {
      x,
      y: 2.84,
      w: 2.08,
      h: 2.42,
      title,
      body,
      accent,
      fill: COLORS.paper,
      largeTitle: true,
    });
  });

  addSectionQuote(
    slide,
    "Пилот реалистичен: проект можно запускать с ограниченного набора дисциплин, быстро собирать обратную связь и расширять контур по мере подтверждения эффекта.",
    1.44,
    5.86,
    10.22,
    true
  );

  addFooter(slide, 11, true);
  addSlideValidation(slide);
}

function buildClosing() {
  const slide = pptx.addSlide();
  addDarkBackground(slide, 0);
  addDeckLabel(slide, "ИТОГОВОЕ ПОЗИЦИОНИРОВАНИЕ", true);

  const closeTitle = "Проект превращает разрозненные материалы института в интеллектуальную образовательную среду";
  slide.addText(closeTitle, {
    ...fit(closeTitle, FONTS.display, {
      x: 0.86,
      y: 1.04,
      w: 7.2,
      h: 1.28,
      minFontSize: 24,
      maxFontSize: 31,
      bold: true,
    }),
    color: COLORS.white,
    bold: true,
    margin: 0,
  });

  const closeBody =
    "Поддержка проекта означает инвестицию не просто в программный продукт, а в современную интеллектуальную инфраструктуру обучения, науки и цифрового развития института.";
  slide.addText(closeBody, {
    ...fit(closeBody, FONTS.body, {
      x: 0.94,
      y: 2.48,
      w: 6.78,
      h: 0.72,
      minFontSize: 12,
      maxFontSize: 16,
    }),
    color: "D2DCF0",
    margin: 0,
  });

  addCard(slide, {
    x: 0.86,
    y: 4.08,
    w: 2.84,
    h: 1.58,
    title: "Для студентов",
    body: "поиск по смыслу, понятные объяснения, задачи на закрепление и персональные аудиолекции.",
    accent: COLORS.cyan,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 3.94,
    y: 4.08,
    w: 2.84,
    h: 1.58,
    title: "Для института",
    body: "рост полезности ресурсов, снижение рутины, локальная безопасность и современный имидж.",
    accent: COLORS.gold,
    fill: COLORS.paper,
    largeTitle: true,
  });
  addCard(slide, {
    x: 7.02,
    y: 4.08,
    w: 2.84,
    h: 1.58,
    title: "Для развития",
    body: "масштабируемая платформа для библиотек, кафедр, исследований и будущих цифровых сервисов.",
    accent: COLORS.teal,
    fill: COLORS.paper,
    largeTitle: true,
  });

  slide.addImage({
    path: ASSETS.logoMark,
    ...imageSizingContain(ASSETS.logoMark, 9.32, 0.78, 3.45, 4.45),
  });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 9.26,
    y: 5.94,
    w: 3.22,
    h: 0.58,
    rectRadius: 0.1,
    fill: { color: COLORS.navy2, transparency: 0 },
    line: { color: COLORS.cyan, pt: 0.8, transparency: 28 },
  });
  slide.addText("Следующий шаг: пилот на ограниченном контуре дисциплин", {
    ...fit("Следующий шаг: пилот на ограниченном контуре дисциплин", FONTS.bodyStrong, {
      x: 9.48,
      y: 6.12,
      w: 2.78,
      h: 0.16,
      minFontSize: 9.2,
      maxFontSize: 11,
      bold: true,
    }),
    color: COLORS.goldSoft,
    margin: 0,
    align: "center",
    bold: true,
  });

  addFooter(slide, 12, true);
  addSlideValidation(slide);
}

function cellLabel(kind) {
  return {
    yes: "да",
    partial: "частично",
    no: "нет",
  }[kind];
}

async function main() {
  buildCover();
  buildProblem();
  buildSolution();
  buildStudents();
  buildInstitute();
  buildInnovation();
  buildReadiness();
  buildComparison();
  buildMarket();
  buildRoadmap();
  buildTeam();
  buildClosing();

  const outPath = path.join(__dirname, "contest_presentation.pptx");
  await pptx.writeFile({ fileName: outPath });
  console.log(`Presentation written to ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
