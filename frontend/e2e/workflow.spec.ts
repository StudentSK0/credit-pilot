import { test, expect, type Page, type Browser } from "@playwright/test";
import path from "node:path";

async function login(page: Page, role: "client" | "bank") {
  await page.goto("/");
  await page
    .getByLabel("Логин", { exact: true })
    .fill(role === "bank" ? "bank" : "client-a");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(
      role === "bank"
        ? (process.env.DEMO_BANK_PASSWORD ?? "demo-bank-local")
        : (process.env.DEMO_CLIENT_PASSWORD ?? "demo-client-a-local"),
    );
  await page
    .getByRole("button", { name: "Войти в кабинет", exact: true })
    .click();
  await expect(page.getByRole("navigation")).toBeVisible();
}

async function pair(browser: Browser) {
  const clientContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5183",
    viewport: { width: 1440, height: 1000 },
  });
  const bankContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5183",
    viewport: { width: 1440, height: 1000 },
  });
  const client = await clientContext.newPage();
  const bank = await bankContext.newPage();
  const errors: string[] = [];
  for (const page of [client, bank])
    page.on("pageerror", (e) => errors.push(e.message));
  await login(client, "client");
  await login(bank, "bank");
  return {
    client,
    bank,
    errors,
    close: async () => {
      await clientContext.close();
      await bankContext.close();
    },
  };
}
async function submitScenario(page: Page, title: string) {
  await page.getByRole("link").filter({ hasText: title }).click();
  await expect(
    page.getByRole("heading", { name: "Расскажите о ваших планах" }),
  ).toBeVisible();
  for (let i = 0; i < 3; i++)
    await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await page
    .getByRole("button", { name: "Отправить заявку", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/applications\/\d+$/);
  await expect(page.locator(".journey-banner")).toContainText(
    "Заявка поступила",
  );
  return Number(page.url().match(/applications\/(\d+)/)![1]);
}
async function check(bank: Page, id: number) {
  await bank.goto(`/#/review/${id}`);
  await bank
    .getByRole("button", { name: "Запустить проверки", exact: true })
    .click();
  await expect(
    bank.getByRole("heading", { name: "Решение сотрудника" }),
  ).toBeVisible();
  await bank.getByRole("tab", { name: "Проверки и риск" }).click();
  await expect(
    bank.getByRole("heading", { name: "ML-оценка риска" }),
  ).toBeVisible();
  await bank.getByRole("tab", { name: "Обзор заявки" }).click();
}
async function offerAndSettle(client: Page, bank: Page) {
  await bank
    .getByLabel("Объяснение для клиента")
    .fill(
      "Денежный остаток покрывает предложенные выплаты с запасом. Условия подтверждены сотрудником.",
    );
  await bank
    .getByRole("button", { name: "Отправить предложение", exact: true })
    .click();
  await expect(bank.locator(".journey-banner")).toContainText(
    "Банк подготовил условия",
  );
  await client.reload();
  await expect(
    client.getByText("Открыть демонстрационный договор"),
  ).toBeVisible();
  await client.getByText("Открыть демонстрационный договор").click();
  await expect(client.locator(".contract-preview pre")).toContainText(
    "не имеет юридической силы",
  );
  await client.getByRole("checkbox").check();
  await client
    .getByRole("button", {
      name: "Принять условия и подписать · демо",
      exact: true,
    })
    .click();
  await expect(client.locator(".journey-banner")).toContainText(
    "Вы приняли условия",
  );
  await bank.reload();
  await bank
    .getByRole("button", { name: "Смоделировать выдачу", exact: true })
    .click();
  await expect(bank.locator(".journey-banner")).toContainText(
    "Демонстрационный путь завершён",
  );
  await client.reload();
  await expect(
    client.getByRole("heading", { name: "Финансирование смоделировано" }),
  ).toBeVisible();
  await client.getByRole("tab", { name: "История действий" }).click();
  await expect(
    client.getByRole("heading", { name: "Смоделирована выдача" }),
  ).toBeVisible();
}

for (const scenario of [
  { code: "growth", title: "Пекарня открывает вторую точку" },
  { code: "clarification", title: "Мастерская уточняет расходы" },
  { code: "risk", title: "Логистика с высокой нагрузкой" },
  { code: "counter", title: "Магазин выбирает посильную сумму" },
])
  test(`${scenario.code}: полный путь через два кабинета`, async ({
    browser,
  }, testInfo) => {
    const p = await pair(browser);
    try {
      const id = await submitScenario(p.client, scenario.title);
      await check(p.bank, id);
      if (scenario.code === "clarification") {
        await p.bank
          .getByRole("button", { name: "Уточнить", exact: true })
          .click();
        await p.bank
          .getByLabel("Вопрос клиенту")
          .fill(
            "Уточните регулярные расходы без разовой покупки и приложите синтетический финансовый отчёт.",
          );
        await p.bank
          .getByRole("button", { name: "Запросить сведения", exact: true })
          .click();
        await expect(p.bank.locator(".journey-banner")).toContainText(
          "Банк задал вопрос",
        );
        await p.client.reload();
        await p.client
          .getByLabel("Операционные расходы", { exact: true })
          .fill("400000.00");
        await p.client
          .getByLabel("Ваше пояснение")
          .fill(
            "Разовая закупка оборудования исключена. Регулярные расходы составляют 400000 рублей в месяц.",
          );
        await p.client
          .getByLabel("Приложить документы")
          .setInputFiles(
            path.join(import.meta.dirname, "fixtures/financial-report.csv"),
          );
        await p.client
          .getByRole("button", { name: "Отправить ответ", exact: true })
          .click();
        await expect(p.client.locator(".journey-banner")).toContainText(
          "Заявка поступила",
        );
        await p.bank.reload();
        await p.bank
          .getByRole("button", { name: "Повторить проверки", exact: true })
          .click();
        await expect(
          p.bank.getByRole("heading", { name: "Решение сотрудника" }),
        ).toBeVisible();
        await expect(
          p.bank.getByRole("link").filter({ hasText: "financial-report.csv" }),
        ).toBeVisible();
      }
      if (scenario.code === "risk") {
        await p.bank
          .getByRole("button", { name: "Отказать", exact: true })
          .click();
        await p.bank
          .getByLabel("Основание решения")
          .selectOption("CREDIT_HISTORY");
        await p.bank
          .getByLabel("Объяснение для клиента")
          .fill(
            "Просрочка 65 дней и высокая долговая нагрузка не позволяют предложить финансирование.",
          );
        await p.bank
          .getByRole("button", { name: "Подтвердить отказ", exact: true })
          .click();
        await expect(p.bank.locator(".journey-banner")).toContainText(
          "Рассмотрение завершено",
        );
        await p.client.reload();
        await expect(
          p.client.getByRole("heading", { name: "Почему банк отказал" }),
        ).toBeVisible();
        await expect(p.client.locator(".decision-card")).toContainText(
          "Просрочка 65 дней",
        );
      } else {
        if (scenario.code === "counter") {
          const value = await p.bank
            .getByLabel("Предлагаемая сумма, ₽")
            .inputValue();
          expect(Number(value)).toBeLessThan(1500000);
          await p.bank.getByRole("tab", { name: "Проверки и риск" }).click();
          await p.bank.screenshot({
            path: testInfo.outputPath("risk-and-counter-offer.png"),
            fullPage: true,
          });
          await p.bank.getByRole("tab", { name: "Обзор заявки" }).click();
        }
        await offerAndSettle(p.client, p.bank);
      }
      await p.bank.goto("/#/");
      await expect(
        p.bank.getByRole("heading", { name: "Воронка финансирования" }),
      ).toBeVisible();
      await expect(p.bank.locator(".decision-table")).toContainText(String(id));
      if (scenario.code === "counter")
        await p.bank.screenshot({
          path: testInfo.outputPath("bank-dashboard.png"),
          fullPage: true,
        });
      expect(p.errors).toEqual([]);
    } finally {
      await p.close();
    }
  });

test("черновик, точность денег, reload, мобильная ширина и чужой маршрут", async ({
  page,
}) => {
  await login(page, "client");
  await page
    .getByRole("link")
    .filter({ hasText: "Пекарня открывает вторую точку" })
    .click();
  await page.getByLabel("Сумма кредита").fill("600000.001");
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("двух знаков");
  await page.getByLabel("Сумма кредита").fill("600000.25");
  await page.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(page).toHaveURL(/applications\/\d+\/edit/);
  await page.reload();
  await expect(page.getByLabel("Сумма кредита")).toHaveValue("600000.25");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Расскажите о ваших планах" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto("/#/review");
  await expect(
    page.getByRole("heading", { name: "Раздел недоступен" }),
  ).toBeVisible();
});
