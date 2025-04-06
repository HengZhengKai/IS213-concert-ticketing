async function fetchSeats(eventID, eventDateTime) {
  const response = await fetch(`http://localhost:5001/seats`);
  return await response.json();
}

const urlParams = new URLSearchParams(window.location.search);
const eventID = urlParams.get("eventID");
const eventDateTime = urlParams.get("eventDateTime");

Vue.createApp({
  data() {
    return {
      seats: [],
    };
  },
  computed: {
    seatRows() {
      // Group seat numbers by row (e.g., seats 1-10 = A, 11-20 = B, etc.)
      const rows = new Set();
      this.seats.forEach(seat => {
        const rowLabel = this.getRowLabel(seat.seatNo);
        rows.add(rowLabel);
      });
      return Array.from(rows).sort();
    },
  },
  async created() {
    this.seats = await fetchSeats(eventID, eventDateTime);
  },
  methods: {
    getRowLabel(seatNo) {
      // Group every 10 seats into one row: 1-10 = A, 11-20 = B, etc.
      const rowIndex = Math.floor((seatNo - 1) / 10);
      return String.fromCharCode(65 + rowIndex); // A, B, C...
    },
    getSeatsByRow(row) {
      return this.seats
        .filter(seat => this.getRowLabel(seat.seatNo) === row)
        .sort((a, b) => a.seatNo - b.seatNo);
    },
    selectSeat(seat) {
      alert(`You selected seat ${seat.seatNo} in category ${seat.category} ($${seat.price})`);
      // Add booking or modal logic here
    }
  }
}).mount("#seatApp");
