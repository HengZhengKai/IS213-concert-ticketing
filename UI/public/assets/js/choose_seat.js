const app = Vue.createApp({
  data() {
    return {
      seats: [],
      selectedSeats: [],
      loading: true,
      categories: ['A', 'B', 'C'],
      seatsByCategory: {
        A: [],
        B: [],
        C: []
      },
      categoryFull: {
        A: false,
        B: false,
        C: false
      },
      maxSelectionLimit: 5,
      selectionError: ''
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
      } catch (e) {
        console.error('Error fetching seats:', e);
      } finally {
        this.loading = false;
      }
    },
    categorizeSeats() {
      this.seatsByCategory = { A: [], B: [], C: [] };
      this.categoryFull = { A: true, B: true, C: true };

      for (const seat of this.seats) {
        const category = seat.category;
        if (this.seatsByCategory[category]) {
          this.seatsByCategory[category].push(seat);
          if (seat.status === 'available') {
            this.categoryFull[category] = false;
          }
        }
      }
    },
    selectSeat(seat) {
      if (seat.status !== 'available') return;
      const index = this.selectedSeats.findIndex(s => s.seatNo === seat.seatNo && s.category === seat.category);
      if (index !== -1) {
        this.selectedSeats.splice(index, 1); // deselect
        this.selectionError = '';
      } else {
        if (this.selectedSeats.length >= this.maxSelectionLimit) {
          this.selectionError = `You can only select a maximum of ${this.maxSelectionLimit} seats.`;
        } else {
          this.selectedSeats.push(seat); // select
          this.selectionError = '';
        }
      }
    },
    isSelected(seat) {
      return this.selectedSeats.some(s => s.seatNo === seat.seatNo && s.category === seat.category);
    },
    seatRowStyle(category) {
      const baseWidths = { A: '100%', B: '80%', C: '60%' };
      return {
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        width: baseWidths[category] || '100%',
        margin: '0 auto',
        opacity: this.categoryFull[category] ? 0.5 : 1,
        pointerEvents: this.categoryFull[category] ? 'none' : 'auto'
      };
    },
    totalSelectedPrice() {
      return this.selectedSeats.reduce((sum, seat) => sum + seat.price, 0).toFixed(2);
    }
  },
  computed: {
    selectedCount() {
      return this.selectedSeats.length;
    },
    canCheckout() {
      return this.selectedSeats.length === 1;
    }
  },
  mounted() {
    this.fetchSeats();
  }
});

app.mount('#app');