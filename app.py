from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# Настраиваем страницу до вывода остальных элементов
st.set_page_config(
    page_title="Анализ розничных продаж",
    layout="wide",
)

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "sales_prepared.csv"


@st.cache_data
def load_data():
    # Читаем подготовленную таблицу и восстанавливаем даты
    data = pd.read_csv(
        DATA_FILE,
        encoding="utf-8-sig",
        dtype={
            "Customer Postal Code": "string",
            "Store Postal Code": "string",
        },
    )
    data["Order Date"] = pd.to_datetime(data["Order Date"])
    data["Ship Date"] = pd.to_datetime(data["Ship Date"])
    return data


def number(value, decimals=0):
    # Форматируем числа с пробелами между разрядами
    return f"{value:,.{decimals}f}".replace(",", " ")


def show_chart(figure):
    # Применяем единый стиль ко всем графикам
    figure.update_layout(
        margin=dict(l=15, r=15, t=60, b=20),
        legend_title_text="",
    )
    st.plotly_chart(figure, width="stretch")


def ranking(data, column, title, limit=10):
    # Строим рейтинг по сумме продаж
    result = (
        data.groupby(column, as_index=False)["Sales"]
        .sum()
        .nlargest(limit, "Sales")
        .sort_values("Sales")
    )
    return px.bar(
        result,
        x="Sales",
        y=column,
        orientation="h",
        title=title,
        labels={"Sales": "Продажи", column: ""},
    )


if not DATA_FILE.exists():
    st.error("Не найден sales_prepared.csv. Сначала запусти prepare_data.py.")
    st.stop()

df = load_data()

st.title("Анализ розничных продаж")
st.caption(
    "Данные за 2022–2024 годы. Одна строка — товарная позиция заказа. "
    "Денежные показатели приведены в единицах исходного файла: "
    "валюта пока не подтверждена."
)

# Размещаем общие фильтры слева
st.sidebar.header("Фильтры")

dates = st.sidebar.date_input(
    "Период продаж",
    value=(
        df["Order Date"].min().date(),
        df["Order Date"].max().date(),
    ),
    min_value=df["Order Date"].min().date(),
    max_value=df["Order Date"].max().date(),
)

regions = st.sidebar.multiselect(
    "Регион продажи — поле Orders.Region",
    options=sorted(df["Region"].unique()),
    default=sorted(df["Region"].unique()),
)

categories = st.sidebar.multiselect(
    "Категория товара",
    options=sorted(df["Category"].unique()),
    default=sorted(df["Category"].unique()),
)

channels = st.sidebar.multiselect(
    "Канал продаж",
    options=sorted(df["Sales Channel"].unique()),
    default=sorted(df["Sales Channel"].unique()),
)

segments = st.sidebar.multiselect(
    "Сегмент клиента",
    options=sorted(df["Segment"].unique()),
    default=sorted(df["Segment"].unique()),
)

# Ждём, пока пользователь выберет обе границы периода
if len(dates) != 2:
    st.info("Выбери начало и конец периода.")
    st.stop()

start_date, end_date = dates

# Применяем все фильтры к одной общей таблице
filtered = df.loc[
    (df["Order Date"].dt.date >= start_date)
    & (df["Order Date"].dt.date <= end_date)
    & df["Region"].isin(regions)
    & df["Category"].isin(categories)
    & df["Sales Channel"].isin(channels)
    & df["Segment"].isin(segments)
].copy()

if filtered.empty:
    st.warning("По выбранным фильтрам нет данных. Измени фильтры слева.")
    st.stop()

# Рассчитываем показатели по отфильтрованным данным
sales = filtered["Sales"].sum()
profit = filtered["Profit"].sum()
order_count = filtered["Order ID"].nunique()
quantity = filtered["Quantity"].sum()
average_check = sales / order_count if order_count else 0

top_region = (
    filtered.groupby("Region")["Sales"].sum().idxmax()
)

# Размещаем карточки показателей в двух рядах
cards = st.columns(4)
cards[0].metric("Продажи", number(sales, 2))
cards[1].metric("Прибыль по данным файла", number(profit, 2))
cards[2].metric("Заказы", number(order_count))
cards[3].metric("Продано единиц", number(quantity))

cards = st.columns(2)
cards[0].metric("Продажи на заказ в выборке", number(average_check, 2))
cards[1].metric("Топ-регион по продажам", top_region)

st.caption(
    "Продажи и прибыль показаны без дополнительного учёта листа Returns. "
    "При фильтре по категории продажи на заказ учитывают только "
    "выбранные позиции, а не полный состав заказа."
)

# Разделяем анализ, модели и прогноз продаж по вкладкам
overview, details, ml_tab, clients_tab, forecast_tab = st.tabs([
    "Обзор",
    "Подробный анализ",
    "Прогноз количества товара",
    "Клиенты",
    "Прогноз продаж",
])
with overview:
    # Группируем продажи и прибыль по месяцам
    monthly = (
        filtered.set_index("Order Date")[["Sales", "Profit"]]
        .resample("MS")
        .sum()
        .reset_index()
    )

    show_chart(px.line(
        monthly,
        x="Order Date",
        y=["Sales", "Profit"],
        markers=True,
        title="Динамика продаж и прибыли по месяцам",
        labels={
            "Order Date": "Месяц",
            "value": "Сумма",
            "variable": "Показатель",
        },
    ))

    left, right = st.columns(2)

    with left:
        show_chart(ranking(
            filtered,
            "Category",
            "Продажи по категориям",
        ))

    with right:
        category_sales = (
            filtered.groupby("Category", as_index=False)["Sales"].sum()
        )
        show_chart(px.pie(
            category_sales,
            names="Category",
            values="Sales",
            hole=0.45,
            title="Доли категорий в продажах",
        ))

    left, right = st.columns(2)

    with left:
        show_chart(ranking(
            filtered,
            "Region",
            "Продажи по регионам",
        ))

    with right:
        show_chart(ranking(
            filtered,
            "Segment",
            "Продажи по сегментам клиентов",
        ))

with details:
    left, right = st.columns(2)

    with left:
        show_chart(ranking(
            filtered,
            "Product Name",
            "Топ-10 товаров по продажам",
        ))

    with right:
        show_chart(ranking(
            filtered,
            "Customer City",
            "Топ-10 городов клиентов",
        ))

    # Создаём тепловую карту продаж по двум категориям
    heatmap = filtered.pivot_table(
        index="Region",
        columns="Category",
        values="Sales",
        aggfunc="sum",
        fill_value=0,
    )
    show_chart(px.imshow(
        heatmap,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Blues",
        title="Продажи: регион × категория",
        labels={
            "x": "Категория",
            "y": "Регион",
            "color": "Продажи",
        },
    ))

    left, right = st.columns(2)

    with left:
        show_chart(px.histogram(
            filtered,
            x="Quantity",
            nbins=14,
            title="Распределение количества в товарной позиции",
            labels={"Quantity": "Количество единиц"},
        ))

    with right:
        show_chart(px.box(
            filtered,
            x="Category",
            y="Sales",
            points=False,
            title="Разброс продаж на одну товарную позицию",
            labels={"Category": "Категория", "Sales": "Продажи"},
        ))

    # Для точечной диаграммы ограничиваем число точек ради скорости
    sample = filtered.sample(
        n=min(3000, len(filtered)),
        random_state=42,
    )
    show_chart(px.scatter(
        sample,
        x="Discount",
        y="Profit",
        color="Category",
        opacity=0.5,
        hover_data=["Product Name", "Quantity", "Sales"],
        title="Скидка и прибыль: до 3000 товарных позиций",
        labels={
            "Discount": "Скидка, доля от 0 до 1",
            "Profit": "Прибыль",
            "Category": "Категория",
        },
    ))

    # Рассчитываем корреляции только числовых показателей
    correlation_columns = [
        "Quantity", "Unit Price", "Discount", "Sales", "Cost", "Profit"
    ]
    correlation = filtered[correlation_columns].corr()

    show_chart(px.imshow(
        correlation,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        aspect="auto",
        color_continuous_scale="RdBu_r",
        title="Матрица корреляций",
    ))
    st.caption(
        "Корреляция показывает связь, а не доказывает причину. "
        "Sales и Profit вычисляются по формулам, поэтому часть связей "
        "возникает из самих расчётов."
    )

    with st.expander("Посмотреть строки данных"):
        st.dataframe(filtered.head(500), hide_index=True)

    # Позволяем выгрузить именно выбранные пользователем данные
    st.download_button(
        label="Скачать отфильтрованные данные",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_sales.csv",
        mime="text/csv",
    )

with ml_tab:
    import joblib

    # Проверяем наличие результатов обучения
    required_files = [
        "quantity_model.joblib",
        "model_metrics.csv",
        "feature_importance.csv",
    ]

    missing_files = [
        name for name in required_files
        if not (PROJECT_DIR / name).exists()
    ]

    if missing_files:
        st.warning(
            "Не найдены результаты обучения: "
            + ", ".join(missing_files)
        )
    else:
        # Загружаем только созданный нами локальный файл модели
        bundle = joblib.load(PROJECT_DIR / "quantity_model.joblib")
        model = bundle["model"]

        metrics = pd.read_csv(
            PROJECT_DIR / "model_metrics.csv",
            encoding="utf-8-sig",
        )
        importance = pd.read_csv(
            PROJECT_DIR / "feature_importance.csv",
            encoding="utf-8-sig",
        )

        st.header("Прогноз количества товара")

        st.write(
            "Модель оценивает количество единиц конкретного товара "
            "в одной позиции заказа. Это не прогноз общего спроса "
            "магазина или продаж за месяц."
        )

        st.info(
            "Обучение: 2022 год. Выбор модели: 2023 год. "
            "После выбора — повторное обучение на 2022–2023 годах. "
            "Финальная проверка: 2024 год. "
            "Фильтры слева не меняют обучение и метрики модели."
        )

        # Показываем результаты финальной проверки
        st.subheader("Сравнение моделей на данных 2024 года")

        test_metrics = metrics.loc[
            metrics["Stage"] == "Test 2024",
            ["Model", "R2", "MAE", "RMSE"],
        ].copy()

        st.dataframe(
            test_metrics.rename(columns={
                "Model": "Модель",
                "R2": "R²",
                "MAE": "MAE, единиц",
                "RMSE": "RMSE, единиц",
            }).round(4),
            hide_index=True,
            width="stretch",
        )

        selected_metrics = test_metrics.loc[
            test_metrics["Model"] == bundle["model_name"]
        ].iloc[0]

        metric_columns = st.columns(3)
        metric_columns[0].metric(
            "R² выбранной модели",
            f"{selected_metrics['R2']:.3f}",
        )
        metric_columns[1].metric(
            "MAE, единиц",
            f"{selected_metrics['MAE']:.3f}",
        )
        metric_columns[2].metric(
            "RMSE, единиц",
            f"{selected_metrics['RMSE']:.3f}",
        )

        st.caption(
            "MAE — средний размер абсолютной ошибки. "
            "RMSE сильнее учитывает большие ошибки. "
            "Для обеих метрик меньше — лучше. "
            "R² не является процентом правильных прогнозов."
        )

        # Отображаем важность исходных признаков случайного леса
        st.subheader("На какие признаки опирается случайный лес")

        feature_names = {
            "Unit Price": "Цена за единицу",
            "Segment": "Сегмент клиента",
            "Discount": "Скидка",
            "Product ID": "Товар",
            "Month Number": "Месяц",
            "Category": "Категория",
            "Region": "Регион продажи",
            "Sales Channel": "Канал продаж",
            "Sub-Category": "Подкатегория",
            "Store Type": "Тип магазина",
            "Weekday Number": "День недели",
        }

        importance["Признак"] = importance["Feature"].map(feature_names)
        importance = importance.sort_values("Importance")

        show_chart(px.bar(
            importance,
            x="Importance",
            y="Признак",
            error_x="Std",
            orientation="h",
            title="Изменение ошибки при перемешивании признака",
            labels={
                "Importance": "Среднее увеличение RMSE",
                "Признак": "",
                "Std": "Разброс оценки",
            },
        ))

        st.caption(
            "Важности рассчитаны на 1200 строках тестовой выборки "
            "с тремя перемешиваниями каждого признака. "
            "Чем больше положительное значение, тем сильнее модель "
            "опирается на признак. Малые отрицательные значения "
            "не означают отрицательного влияния на количество. "
            "Этот график не доказывает причинные связи."
        )

        st.divider()
        st.subheader("Получить прогноз")

        # Используем полный набор данных, а не отфильтрованную выборку
        # Известные товары берём из периода итогового обучения
        known_products = (
            df.loc[df["Year"] <= 2023]
            .drop_duplicates("Product ID")
            .sort_values("Product Name")
            .set_index("Product ID")
        )

        product_id = st.selectbox(
            "Выбери товар",
            options=known_products.index.tolist(),
            format_func=lambda value: (
                f"{known_products.loc[value, 'Product Name']} "
                f"({value})"
            ),
            key="prediction_product",
        )

        product = known_products.loc[product_id]

        st.caption(
            f"Категория: {product['Category']}. "
            f"Подкатегория: {product['Sub-Category']}. "
            "Цена задаётся до применения скидки."
        )

        # Товар выбирается вне формы, чтобы цена обновлялась при его смене
        with st.form("quantity_prediction_form"):
            left, right = st.columns(2)

            with left:
                prediction_date = st.date_input(
                    "Дата предполагаемой покупки",
                    value=pd.Timestamp("2024-06-15").date(),
                    key="prediction_date",
                )

                unit_price = st.number_input(
                    "Цена за единицу до скидки",
                    min_value=0.01,
                    value=float(product["Unit Price"]),
                    step=1.0,
                    key=f"prediction_price_{product_id}",
                )

                discount_percent = st.slider(
                    "Скидка, %",
                    min_value=0,
                    max_value=50,
                    value=10,
                    step=5,
                )

            with right:
                region = st.selectbox(
                    "Регион продажи",
                    options=sorted(df["Region"].unique()),
                    key="prediction_region",
                )

                segment = st.selectbox(
                    "Сегмент клиента",
                    options=sorted(df["Segment"].unique()),
                    key="prediction_segment",
                )

                sales_channel = st.selectbox(
                    "Канал продаж",
                    options=sorted(df["Sales Channel"].unique()),
                    key="prediction_channel",
                )

            store_type = st.selectbox(
                "Тип магазина",
                options=sorted(df["Store Type"].unique()),
                key="prediction_store_type",
            )

            submitted = st.form_submit_button("Рассчитать прогноз")

        if submitted:
            # Формируем одну строку с теми же признаками, что при обучении
            input_data = pd.DataFrame([{
                "Product ID": product_id,
                "Category": product["Category"],
                "Sub-Category": product["Sub-Category"],
                "Region": region,
                "Segment": segment,
                "Sales Channel": sales_channel,
                "Store Type": store_type,
                "Unit Price": unit_price,
                "Discount": discount_percent / 100,
                "Month Number": prediction_date.month,
                "Weekday Number": prediction_date.weekday() + 1,
            }])

            prediction = float(
                model.predict(input_data[bundle["features"]])[0]
            )

            st.success(
                f"Прогноз количества: {prediction:.2f} единицы "
                "в одной товарной позиции заказа."
            )

            st.write(f"Использованная модель: {bundle['model_name']}.")

            st.caption(
                "Дробное число — оценка среднего количества, "
                "а не требование купить часть товара. "
                f"На тестовых данных средняя абсолютная ошибка модели "
                f"составила {selected_metrics['MAE']:.2f} единицы. "
                "Это общая оценка качества, а не интервал ошибки "
                "для конкретного прогноза."
            )

            # Предупреждаем о параметрах вне наблюдавшегося периода
            if prediction_date.year not in [2022, 2023, 2024]:
                st.warning(
                    "Выбрана дата вне периода исходных данных. "
                    "Модель использует месяц и день недели, "
                    "но не учитывает долгосрочные изменения рынка."
                )

            # Сравниваем введённую цену с диапазоном обучения
            training_prices = df.loc[
                (df["Year"] <= 2023)
                & (df["Product ID"] == product_id),
                "Unit Price",
            ]

            if not (
                training_prices.min() <= unit_price <= training_prices.max()
            ):
                st.warning(
                    "Цена выходит за наблюдавшийся диапазон "
                    "этого товара в обучающих данных. "
                    "Такой прогноз следует считать экспериментальным."
                )

            # Показываем введённые параметры для проверки
            with st.expander("Параметры, переданные модели"):
                st.dataframe(input_data, hide_index=True)

        st.caption(
            "Форма — учебная демонстрация. Не все сочетания канала "
            "и типа магазина обязательно встречались в данных. "
            "Изменение параметров не является доказательством "
            "эффекта реального бизнес-решения."
        )

with clients_tab:
    st.header("Группы клиентов по покупательскому поведению")

    st.info(
        "Анализ на 01.01.2025 по покупкам за 2022–2024 годы. "
        "Фильтры слева не пересчитывают эту сегментацию. "
        "Показатели продаж приведены без вычитания возвратов."
    )

    client_files = [
        "clients_clustered.csv",
        "cluster_profiles.csv",
        "cluster_scores.csv",
    ]

    missing_client_files = [
        name for name in client_files
        if not (PROJECT_DIR / name).exists()
    ]

    if missing_client_files:
        st.warning(
            "Не найдены файлы кластеризации: "
            + ", ".join(missing_client_files)
        )
    else:
        # Загружаем готовые результаты, не обучая KMeans заново
        client_data = pd.read_csv(
            PROJECT_DIR / "clients_clustered.csv",
            encoding="utf-8-sig",
        )
        profiles = pd.read_csv(
            PROJECT_DIR / "cluster_profiles.csv",
            encoding="utf-8-sig",
        )
        cluster_scores = pd.read_csv(
            PROJECT_DIR / "cluster_scores.csv",
            encoding="utf-8-sig",
        )

        # Номера кластеров являются условными метками, а не рейтингом
        client_data["Группа"] = (
            "Группа " + client_data["Cluster"].astype(str)
        )
        profiles["Группа"] = (
            "Группа " + profiles["Cluster"].astype(str)
        )

        best_cluster_count = int(
            cluster_scores.sort_values(
                "Silhouette",
                ascending=False,
            ).iloc[0]["Clusters"]
        )
        best_silhouette = float(
            cluster_scores.loc[
                cluster_scores["Clusters"] == best_cluster_count,
                "Silhouette",
            ].iloc[0]
        )

        cards = st.columns(3)
        cards[0].metric("Клиентов с покупками", number(len(client_data)))
        cards[1].metric("Выбрано групп", best_cluster_count)
        cards[2].metric("Силуэт", f"{best_silhouette:.3f}")

        st.write(
            "Для каждого клиента рассчитали давность последней покупки, "
            "число уникальных заказов и общую сумму продаж. "
            "Применили log1p и StandardScaler, затем KMeans. "
            "Число групп выбрали по максимальному силуэту "
            "среди вариантов от 2 до 6."
        )

        # Выводим показатели групп в исходных единицах
        profile_view = profiles[[
            "Группа",
            "Clients",
            "Clients_Percent",
            "Recency_Mean",
            "Orders_Mean",
            "Sales_Mean",
            "Sales_Percent",
        ]].rename(columns={
            "Clients": "Клиентов",
            "Clients_Percent": "Доля клиентов, %",
            "Recency_Mean": "Дней с покупки, среднее",
            "Orders_Mean": "Заказов, среднее",
            "Sales_Mean": "Сумма покупок, среднее",
            "Sales_Percent": "Доля продаж, %",
        })

        st.subheader("Характеристики групп")
        st.dataframe(
            profile_view.round(2),
            hide_index=True,
            width="stretch",
        )

        left, right = st.columns(2)

        with left:
            show_chart(px.pie(
                profiles,
                names="Группа",
                values="Clients",
                hole=0.45,
                title="Распределение клиентов по группам",
            ))

        with right:
            show_chart(px.pie(
                profiles,
                names="Группа",
                values="Sales_Total",
                hole=0.45,
                title="Вклад групп в продажи",
            ))

        # Показываем всех клиентов на двумерном графике
        # KMeans использовал три признака, а здесь отображаются только два
        show_chart(px.scatter(
            client_data,
            x="Frequency",
            y="Monetary",
            color="Группа",
            opacity=0.6,
            hover_data=["Customer ID", "Recency"],
            title="Клиенты: число заказов и сумма покупок",
            labels={
                "Frequency": "Уникальных заказов за весь период",
                "Monetary": "Сумма покупок за весь период",
                "Customer ID": "Клиент",
                "Recency": "Дней с последней покупки",
            },
        ))

        show_chart(px.box(
            client_data,
            x="Группа",
            y="Recency",
            points=False,
            title="Давность последней покупки по группам",
            labels={
                "Recency": "Дней до даты анализа 01.01.2025",
            },
        ))

        st.caption(
            "Меньше дней с последней покупки означает более недавнюю покупку. "
            "Двумерный график не показывает всё пространство признаков, "
            "в котором выполнялась кластеризация."
        )

        with st.expander("Как выбирали число групп"):
            st.dataframe(
                cluster_scores.round(4),
                hide_index=True,
                width="stretch",
            )
            st.write(
                "Силуэт оценивает разделённость групп, а не точность прогноза. "
                "ARI показывает сходство двух запусков на одних данных. "
                "Это не проверка устойчивости групп во времени."
            )

        with st.expander("Посмотреть клиентов"):
            st.dataframe(
                client_data,
                hide_index=True,
                width="stretch",
            )

        st.download_button(
            "Скачать клиентов с номерами групп",
            data=client_data.to_csv(index=False).encode("utf-8-sig"),
            file_name="clients_with_clusters.csv",
            mime="text/csv",
            key="download_client_clusters",
        )

        st.warning(
            "Группы описывают прошлые покупки, а не гарантируют будущие. "
            "Клиенты без покупок не включены. "
            "Дата регистрации и длительность наблюдения каждого клиента "
            "не учитывались. Номер группы не является оценкой человека."
        )

with forecast_tab:
    import joblib

    st.header("Прогноз общей суммы продаж по месяцам")

    st.info(
        "Прогноз строится для всех продаж исходного набора. "
        "Фильтры слева не изменяют эту модель и её результаты. "
        "Карточки над вкладками относятся к отфильтрованной "
        "выборке, а не к этому прогнозу."
    )

    forecast_files = [
        "monthly_sales.csv",
        "monthly_forecast_metrics.csv",
        "monthly_forecast_test.csv",
        "monthly_forecast_model.joblib",
    ]

    missing_forecast_files = [
        name for name in forecast_files
        if not (PROJECT_DIR / name).exists()
    ]

    if missing_forecast_files:
        st.warning(
            "Не найдены файлы: "
            + ", ".join(missing_forecast_files)
            + ". Сначала запусти prepare_monthly.py, "
            "затем forecast_monthly.py."
        )
    else:
        forecast_history = pd.read_csv(
            PROJECT_DIR / "monthly_sales.csv",
            encoding="utf-8-sig",
        )
        forecast_metrics = pd.read_csv(
            PROJECT_DIR / "monthly_forecast_metrics.csv",
            encoding="utf-8-sig",
        )
        forecast_test = pd.read_csv(
            PROJECT_DIR / "monthly_forecast_test.csv",
            encoding="utf-8-sig",
        )

        # Загружаем только созданную нами локальную модель
        forecast_bundle = joblib.load(
            PROJECT_DIR / "monthly_forecast_model.joblib"
        )
        monthly_model = forecast_bundle["model"]

        for table in [forecast_history, forecast_test]:
            table["Month"] = pd.to_datetime(table["Month"])
            table.sort_values("Month", inplace=True)
            table.reset_index(drop=True, inplace=True)

        training_start = pd.Timestamp(
            forecast_bundle["training_start"]
        )
        training_end = pd.Timestamp(
            forecast_bundle["training_end"]
        )

        # Индексы времени должны продолжать именно период обучения
        expected_history_dates = pd.date_range(
            training_start,
            training_end,
            freq="MS",
        )

        history_matches_model = (
            forecast_history["Month"].tolist()
            == expected_history_dates.tolist()
        )

        if not history_matches_model:
            st.error(
                "Период месячной таблицы не совпадает с периодом "
                "сохранённой модели. Повторно запусти "
                "forecast_monthly.py, затем обнови страницу."
            )
        else:
            st.write(
                "Модель прогнозирует общую сумму продаж за месяц. "
                "Линейная регрессия учитывает общий тренд "
                "и особенности календарных месяцев."
            )

            st.subheader("1. Проверка на данных 2024 года")

            st.write(
                "Обучение: 2022–2023 годы. Проверка: 2024 год. "
                "Все 12 тестовых прогнозов построены из конца "
                "2023 года без обновления по факту 2024 года."
            )

            st.dataframe(
                forecast_metrics.rename(columns={
                    "Method": "Метод",
                    "WAPE Percent": "WAPE, %",
                }).round(2),
                hide_index=True,
                width="stretch",
            )

            regression_row = forecast_metrics.loc[
                forecast_metrics["Method"] == "Тренд и сезонность"
            ].iloc[0]

            baseline_row = forecast_metrics.loc[
                forecast_metrics["Method"] == "Сезонный ориентир"
            ].iloc[0]

            cards = st.columns(3)
            cards[0].metric(
                "MAE регрессии",
                number(regression_row["MAE"], 2),
            )
            cards[1].metric(
                "RMSE регрессии",
                number(regression_row["RMSE"], 2),
            )
            cards[2].metric(
                "WAPE регрессии",
                f"{regression_row['WAPE Percent']:.2f}%",
            )

            st.caption(
                "MAE — средняя абсолютная ошибка за месяц. "
                "RMSE сильнее учитывает большие ошибки. "
                "WAPE — сумма абсолютных ошибок относительно "
                "общего объёма фактических продаж, в процентах. "
                "Меньше — лучше. WAPE не является долей "
                "неправильных прогнозов."
            )

            if all(
                regression_row[column] < baseline_row[column]
                for column in ["MAE", "RMSE", "WAPE Percent"]
            ):
                st.success(
                    "На тестовом 2024 году регрессия показала "
                    "меньшую ошибку по всем трём метрикам."
                )

            test_chart = forecast_test.rename(columns={
                "Sales": "Фактические продажи",
                "Seasonal Naive": "Сезонный ориентир",
                "Trend and Seasonality": "Тренд и сезонность",
            })

            show_chart(px.line(
                test_chart,
                x="Month",
                y=[
                    "Фактические продажи",
                    "Сезонный ориентир",
                    "Тренд и сезонность",
                ],
                markers=True,
                title="2024 год: фактические продажи и прогнозы",
                labels={
                    "Month": "Месяц",
                    "value": "Продажи, денежные единицы файла",
                    "variable": "Ряд",
                },
            ))

            st.caption(
                "Сезонный ориентир использует продажи того же "
                "месяца предыдущего года. "
                "Преимущество по итогам года не означает "
                "преимущества в каждом отдельном месяце."
            )

            with st.expander("Тестовые прогнозы по месяцам"):
                test_view = test_chart.copy()
                test_view["Month"] = (
                    test_view["Month"].dt.strftime("%m.%Y")
                )
                test_view.rename(
                    columns={"Month": "Месяц"},
                    inplace=True,
                )

                numeric_columns = test_view.select_dtypes(
                    include="number"
                ).columns
                test_view[numeric_columns] = (
                    test_view[numeric_columns].round(2)
                )

                st.dataframe(
                    test_view,
                    hide_index=True,
                    width="stretch",
                )

            st.divider()
            st.subheader("2. Интерактивный прогноз")

            st.write(
                "После проверки модель повторно обучили "
                "на всех данных за 2022–2024 годы. "
                "Выбери, на сколько следующих месяцев "
                "рассчитать прогноз."
            )

            horizon = st.slider(
                "Горизонт прогноза, месяцев",
                min_value=1,
                max_value=12,
                value=3,
                step=1,
                key="monthly_forecast_horizon",
            )

            # Продолжаем временной индекс обученной модели
            future_dates = pd.date_range(
                start=training_end + pd.offsets.MonthBegin(1),
                periods=horizon,
                freq="MS",
            )

            dynamic_future = pd.DataFrame({
                "Month": future_dates,
                "Time Index": range(
                    len(expected_history_dates),
                    len(expected_history_dates) + horizon,
                ),
                "Calendar Month": future_dates.month,
            })

            dynamic_future["Forecast"] = monthly_model.predict(
                dynamic_future[forecast_bundle["features"]]
            )

            # Для горизонта до 12 месяцев все значения ориентира
            # берутся из последнего известного года
            history_by_date = forecast_history.set_index(
                "Month"
            )["Sales"]

            previous_year_dates = (
                dynamic_future["Month"]
                - pd.DateOffset(years=1)
            )

            dynamic_future["Seasonal Naive"] = (
                history_by_date.reindex(
                    pd.DatetimeIndex(previous_year_dates)
                ).to_numpy()
            )

            st.caption(
                f"Последний месяц обучения: "
                f"{training_end:%m.%Y}. "
                f"Период прогноза: "
                f"{future_dates.min():%m.%Y} — "
                f"{future_dates.max():%m.%Y}. "
                "При изменении горизонта прогноз пересчитывается "
                "сохранённой моделью без повторного обучения."
            )

            if (dynamic_future["Forecast"] < 0).any():
                st.warning(
                    "Есть отрицательные прогнозы продаж. "
                    "Они не обрезаны до нуля: "
                    "для использования потребуется пересмотреть модель."
                )

            cards = st.columns(2)
            cards[0].metric(
                "Месяцев в прогнозе",
                horizon,
            )
            cards[1].metric(
                "Сумма прогноза за выбранный период",
                number(dynamic_future["Forecast"].sum(), 2),
            )

            history_plot = forecast_history[
                ["Month", "Sales"]
            ].rename(columns={"Sales": "Значение"})
            history_plot["Ряд"] = "Фактические продажи"

            future_plot = dynamic_future[
                ["Month", "Forecast"]
            ].rename(columns={"Forecast": "Значение"})

            # Соединяем прогноз с последним известным фактом
            forecast_connection = pd.concat(
                [
                    history_plot[["Month", "Значение"]].tail(1),
                    future_plot,
                ],
                ignore_index=True,
            )
            forecast_connection["Ряд"] = "Прогноз регрессии"

            combined_plot = pd.concat(
                [history_plot, forecast_connection],
                ignore_index=True,
            )

            show_chart(px.line(
                combined_plot,
                x="Month",
                y="Значение",
                color="Ряд",
                line_dash="Ряд",
                line_dash_map={
                    "Фактические продажи": "solid",
                    "Прогноз регрессии": "dash",
                },
                color_discrete_map={
                    "Фактические продажи": "#1f77b4",
                    "Прогноз регрессии": "#ff7f0e",
                },
                markers=True,
                title=(
                    "История продаж и прогноз: "
                    f"{horizon} мес."
                ),
                labels={
                    "Month": "Месяц",
                    "Значение": "Продажи, денежные единицы файла",
                    "Ряд": "",
                },
            ))

            st.caption(
                "Пунктир начинается с последнего фактического "
                "месяца только для соединения линий. "
                "При увеличении горизонта ранее рассчитанные "
                "месяцы не меняются: добавляются новые."
            )

            future_view = dynamic_future[[
                "Month",
                "Forecast",
                "Seasonal Naive",
            ]].copy()

            future_view["Month"] = (
                future_view["Month"].dt.strftime("%m.%Y")
            )
            future_view.rename(columns={
                "Month": "Месяц",
                "Forecast": "Прогноз регрессии",
                "Seasonal Naive": "Сезонный ориентир",
            }, inplace=True)

            numeric_columns = future_view.select_dtypes(
                include="number"
            ).columns
            future_view[numeric_columns] = (
                future_view[numeric_columns].round(2)
            )

            st.dataframe(
                future_view,
                hide_index=True,
                width="stretch",
            )

            st.download_button(
                "Скачать прогноз на выбранный период",
                data=dynamic_future[[
                    "Month",
                    "Forecast",
                    "Seasonal Naive",
                ]].to_csv(index=False).encode("utf-8-sig"),
                file_name=f"monthly_forecast_{horizon}_months.csv",
                mime="text/csv",
                key="download_dynamic_monthly_forecast",
            )

            st.warning(
                "Это прогноз из конца 2024 года, "
                "а не относительно сегодняшней даты. "
                "Фактических продаж за 2025 год в наборе нет. "
                "Метрики выше относятся к проверке на 2024 году "
                "и не гарантируют такую же ошибку в будущем. "
                "Интервалы неопределённости не рассчитаны. "
                "Модель не учитывает будущие акции, изменение "
                "ассортимента и внешние изменения рынка. "
                "Продажи указаны в денежных единицах исходного "
                "файла без дополнительного вычитания возвратов."
            )