import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Streamlit file uploader
st.title("SLA Dashboard for CT Exams")

uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded_file is not None:
    # Load the uploaded Excel file
    df = pd.read_excel(uploaded_file)

    # Filter the data for 'CT' modality and 'Pronto Atendimento'
    filtered_df = df[(df['MODALIDADE'] == 'CT') & (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento')]

    # Convert the relevant time columns to datetime, using dayfirst=True to handle DD-MM-YYYY format
    filtered_df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(filtered_df['DATA_HORA_PRESCRICAO'], dayfirst=True, errors='coerce')
    filtered_df['STATUS_ALAUDAR'] = pd.to_datetime(filtered_df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')

    # Drop rows where the date conversion failed (i.e., rows with NaT in either datetime column)
    filtered_df = filtered_df.dropna(subset=['DATA_HORA_PRESCRICAO', 'STATUS_ALAUDAR'])

    # Sidebar for selecting UNIDADE and Date
    st.sidebar.header("Filter Options")

    # UNIDADE selection
    unidade_options = filtered_df['UNIDADE'].dropna().unique()
    selected_unidade = st.sidebar.selectbox('Select UNIDADE', options=unidade_options)

    # Apply UNIDADE filter before further processing
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_unidade]

    # Date selection (specific day or range)
    date_option = st.sidebar.radio("Select Date Option", ['Specific Day', 'Date Range'])

    if date_option == 'Specific Day':
        selected_date = st.sidebar.date_input("Choose a day", value=pd.to_datetime('today'))
        # Filter for the specific day (start and end of the day)
        start_date = pd.to_datetime(selected_date)
        end_date = start_date + pd.DateOffset(days=1) - pd.Timedelta(seconds=1)  # Include the full day until 23:59:59
        filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'] >= start_date) & 
                                  (filtered_df['DATA_HORA_PRESCRICAO'] <= end_date)]
    else:
        start_date, end_date = st.sidebar.date_input("Select date range", value=(pd.to_datetime('today') - pd.DateOffset(days=7), pd.to_datetime('today')))
        # Ensure the date range includes the entire start and end days
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'] >= start_date) & 
                                  (filtered_df['DATA_HORA_PRESCRICAO'] <= end_date)]

    # Check if there is data to display after filtering
    if filtered_df.empty:
        st.write("No data available for the selected UNIDADE and date range.")
    else:
        # Display the filtered dataframe
        st.write(f"### Filtered Data for {selected_unidade}")
        st.dataframe(filtered_df)

        # Calculate the time difference (in hours)
        filtered_df['PROCESS_TIME_HOURS'] = (filtered_df['STATUS_ALAUDAR'] - filtered_df['DATA_HORA_PRESCRICAO']).dt.total_seconds() / 3600

        # Classify into time intervals
        def classify_sla(hours):
            if pd.isnull(hours):
                return 'No Data'
            if hours <= 1:
                return 'Within SLA'
            elif hours <= 2:
                return '1 to 2 hours'
            elif hours <= 3:
                return '2 to 3 hours'
            else:
                return 'Over 3 hours'

        # Apply the classification
        filtered_df['SLA_STATUS'] = filtered_df['PROCESS_TIME_HOURS'].apply(classify_sla)

        # Flagging cases that exceed the 1-hour limit as 'FORA DO PRAZO'
        filtered_df['FORA_DO_PRAZO'] = filtered_df['PROCESS_TIME_HOURS'] > 1

        # Display the dataframe with the analysis columns (SLA status, process time, etc.)
        st.write(f"### Processed Data with SLA Status for {selected_unidade}")
        st.dataframe(filtered_df[['DATA_HORA_PRESCRICAO', 'STATUS_ALAUDAR', 'PROCESS_TIME_HOURS', 'SLA_STATUS', 'FORA_DO_PRAZO']])

        # Calculate totals and averages
        total_patients = filtered_df.shape[0]
        avg_process_time = filtered_df['PROCESS_TIME_HOURS'].mean()

        # Top 10 Worst Days (most "FORA DO PRAZO" exams)
        filtered_df['DATE'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.date
        filtered_df['DAY_OF_WEEK'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.day_name()

        # Create time periods (morning, afternoon, night)
        def get_period(hour):
            if 6 <= hour < 12:
                return 'Morning'
            elif 12 <= hour < 18:
                return 'Afternoon'
            else:
                return 'Night'

        filtered_df['HOUR'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.hour
        filtered_df['TIME_PERIOD'] = filtered_df['HOUR'].apply(get_period)

        # Group by Date, Day of Week, and Time Period for the worst days analysis
        worst_days = filtered_df[filtered_df['FORA_DO_PRAZO']].groupby(['DATE', 'DAY_OF_WEEK', 'TIME_PERIOD']).size().reset_index(name='FORA_DO_PRAZO_COUNT')
        worst_days = worst_days.sort_values(by='FORA_DO_PRAZO_COUNT', ascending=False).head(10)

        if worst_days.shape[0] > 0:
            st.write("### Top 10 Worst Days by FORA DO PRAZO Count with Day and Period")
            st.dataframe(worst_days)

        # Heatmap for day of the week and time of day
        heatmap_data = filtered_df.groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)

        # Display the heatmap for number of exams by day and period
        st.write(f"### Heatmap of Exams by Day and Time Period for {selected_unidade}")
        fig4, ax4 = plt.subplots(figsize=(10, 6))
        sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='coolwarm', ax=ax4)
        ax4.set_title('Number of Exams by Day and Time Period')
        st.pyplot(fig4)

        # Correlate heatmap with SLA status (exams within SLA vs outside SLA)
        sla_heatmap_data = filtered_df[filtered_df['SLA_STATUS'] == 'Within SLA'].groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)

        st.write(f"### Heatmap of Exams within SLA by Day and Time Period for {selected_unidade}")
        fig5, ax5 = plt.subplots(figsize=(10, 6))
        sns.heatmap(sla_heatmap_data, annot=True, fmt='d', cmap='Blues', ax=ax5)
        ax5.set_title('Exams Within SLA by Day and Time Period')
        st.pyplot(fig5)

        # Correlate worst days with heatmap
        st.write("### Highlighting Top 10 Worst Days on Heatmap")
        worst_day_labels = worst_days['DATE'].astype(str).tolist()

        filtered_df['DAY'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.date.astype(str)
        filtered_df['WORST_DAY_FLAG'] = filtered_df['DAY'].apply(lambda x: 1 if x in worst_day_labels else 0)

        # Group for heatmap display: show count of FORA DO PRAZO by day of the week and time period for the worst days
        worst_day_heatmap_data = filtered_df[filtered_df['WORST_DAY_FLAG'] == 1].groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)

        # Create annotation text for the heatmap with both "FORA DO PRAZO" counts and dates
        def create_annotation_text(row, col, data, worst_days):
            if data.at[row, col] > 0:
                # Find matching date from worst_days for the row and col
                matched_rows = worst_days[(worst_days['DAY_OF_WEEK'] == row) & (worst_days['TIME_PERIOD'] == col)]
                if not matched_rows.empty:
                    # Combine dates and count in the annotation text
                    dates = ', '.join(matched_rows['DATE'].astype(str).values)
                    return f"{data.at[row, col]} ({dates})"
            return ""

        # Apply the annotation function
        annotations = [[create_annotation_text(row, col, worst_day_heatmap_data, worst_days)
                        for col in worst_day_heatmap_data.columns] for row in worst_day_heatmap_data.index]

        # Display the heatmap for the top 10 worst days with "FORA DO PRAZO" count and date as annotations
        fig6, ax6 = plt.subplots(figsize=(10, 6))
        sns.heatmap(worst_day_heatmap_data, annot=annotations, fmt='', cmap='Reds', ax=ax6, cbar=False)
        ax6.set_title('Number of FORA DO PRAZO Exams on Top 10 Worst Days (with Dates)')
        st.pyplot(fig6)

        # Total Patients Processed and Average Process Time
        st.write(f"**Total Patients Processed**: {total_patients}")
        st.write(f"**Average Process Time (in hours)**: {avg_process_time:.2f}")

        # SLA Violations Plot (Pie Chart)
        st.write(f"### SLA Violations (FORA DO PRAZO) for {selected_unidade}")
        fig2, ax2 = plt.subplots()
        violation_data = [filtered_df[filtered_df['FORA_DO_PRAZO']].shape[0], filtered_df[~filtered_df['FORA_DO_PRAZO']].shape[0]]
        labels = ['FORA DO PRAZO', 'Within SLA']
        ax2.pie(violation_data, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#ff9999', '#99ff99'])
        ax2.set_title('SLA Violations')
        st.pyplot(fig2)

        # Average Process Time by SLA Category (Bar Chart)
        st.write(f"### Average Process Time by SLA Category for {selected_unidade}")
        avg_process_by_sla = filtered_df.groupby('SLA_STATUS')['PROCESS_TIME_HOURS'].mean()
        fig3, ax3 = plt.subplots()
        avg_process_by_sla.plot(kind='bar', ax=ax3, color='#66b3ff')
        ax3.set_ylabel('Average Time (hours)')
        ax3.set_title('Average Process Time by SLA Category')
        st.pyplot(fig3)

else:
    st.write("Please upload an Excel file to continue.")
