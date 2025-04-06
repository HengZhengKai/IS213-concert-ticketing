const app = Vue.createApp({
  data() {
    return {
      seats: [],
      selectedSeat: null,
      loading: true,
      categories: ['A', 'B', 'C'],
      seatsByCategory: {
        A: [],
        B: [],
        C: []
      }
    };
  },
  methods: {
    getQueryParams() {
      const params = new URLSearchParams(window.location.search);
      return {
        eventID: params.get('eventID'),
        eventDateTime: decodeURIComponent(params.get('eventDateTime'))
      };
    },
    async fetchSeats() {
      const { eventID, eventDateTime } = this.getQueryParams();
      const encodedDateTime = encodeURIComponent(eventDateTime);
      try {
        const res = await fetch(`http://localhost:5002/seats/${eventID}/${encodedDateTime}`);
        const data = await res.json();
        if (data.code === 200) {
          this.seats = data.data;
          this.categorizeSeats();
        } else {
          console.error('Failed to fetch seats:', data.message);
        }
        console.log("Fetching seats from:", `http://localhost:5002/seats/${eventID}/${encodedDateTime}`);
        console.log("Raw eventDateTime param:", eventDateTime);

      } catch (e) {
        console.error('Error fetching seats:', e);
      } finally {
        this.loading = false;
      }
    },
    categorizeSeats() {
      this.seatsByCategory = { A: [], B: [], C: [] };
      for (const seat of this.seats) {
        // Ensure there's a valid category
        if (this.seatsByCategory[seat.category]) {
          this.seatsByCategory[seat.category].push(seat);
        }
      }
    },
    selectSeat(seat) {
      if (seat.status !== 'available') return;
      this.selectedSeat = seat;
    }
  },
  mounted() {
    this.fetchSeats();
  }
});

app.mount('#app');
