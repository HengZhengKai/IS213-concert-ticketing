const app = Vue.createApp({
  data() {
    return {
      eventName: '',
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
      selectionError: '',
      showError: false,
      showSignupModal: false,
      attendeeForms: [],
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
        this.selectedSeats.splice(index, 1);
        this.attendeeForms.splice(index, 1);
        this.selectionError = '';
        this.showError = false;
      } else {
        if (this.selectedSeats.length >= this.maxSelectionLimit) {
          this.selectionError = `You can only select a maximum of ${this.maxSelectionLimit} seats.`;
          this.showError = true;
          setTimeout(() => this.showError = false, 3000);
        } else {
          this.selectedSeats.push(seat);
          this.attendeeForms.push({ name: '', email: '', phone: '', dietaryRestrictions: '', specialRequests: '' });
          this.selectionError = '';
          this.showError = false;
        }
      }
    },
    addAttendeeForm() {
      if (this.attendeeForms.length < this.selectedSeats.length) {
        this.attendeeForms.push({ name: '', email: '', phone: '', dietaryRestrictions: '', specialRequests: '' });
      } else {
        this.selectionError = `You can only add as many attendees as selected seats.`;
        this.showError = true;
        setTimeout(() => this.showError = false, 3000);
      }
    },
    removeAttendeeForm(index) {
      if (this.attendeeForms.length > 1) {
        this.attendeeForms.splice(index, 1);
        this.selectedSeats.splice(index, 1);
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
    },
    categoryNotice(category) {
      if (this.categoryFull[category]) {
        return `⚠️ All seats in Category ${category} are filled.`;
      } else {
        const availableSeats = this.seatsByCategory[category].filter(seat => seat.status === 'available').length;
        return `✅ ${availableSeats} seat(s) available in Category ${category}`;
      }
    },
    openSignupModal() {
      if (this.canCheckout) {
        this.$nextTick(() => {
          const modalEl = document.getElementById("signupModal");
          if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
          }
        });
      } else {
        this.selectionError = 'Please select at least one seat before proceeding.';
        this.showError = true;
        setTimeout(() => this.showError = false, 3000);
      }
    },
    validateEmail(email) {
      const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return regex.test(email);
    },
    validatePhone(phone) {
      const regex = /^\+\d{1,3}\d{7,12}$/;
      return regex.test(phone);
    },
    async validateForm() {
      console.log("button");
      const categories = [...new Set(this.selectedSeats.map(seat => seat.category))].sort();
      const categoryLabel = categories.join(', ');
      const productName = `${this.eventName} - Category ${categoryLabel}`;
    
      // Validate attendee forms
      for (const form of this.attendeeForms) {
        if (!form.name || !this.validateEmail(form.email) || !this.validatePhone(form.phone)) {
          this.selectionError = 'Please ensure all attendee emails and phone numbers are valid.';
          this.showError = true;
          setTimeout(() => this.showError = false, 3000);
          return false;
        }
      }
    
      this.selectionError = '';
      this.showError = false;
    
      try {
        const { eventID, eventDateTime } = this.getQueryParams();
        const encodedDateTime = encodeURIComponent(eventDateTime);
        const cancelUrl = `http://localhost:8080/choose_seat.html?eventID=${eventID}&eventDateTime=${encodedDateTime}`;

        const response = await fetch("http://localhost:5007/start-checkout", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            mode: "payment",
            success_url: "http://localhost:8080/my_tickets.html?session_id={CHECKOUT_SESSION_ID}",
            cancel_url: cancelUrl,
            currency: "sgd", 
            product_name: productName,
            unit_amount: this.selectedSeats.length > 0 ? this.selectedSeats[0].price * 100 : 0, 
            quantity: this.selectedSeats.length

          })
        });
    
        const result = await response.json();
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
        } else {
          console.error("No checkout_url found in response:", result);
          this.selectionError = "Something went wrong. Please try again.";
          this.showError = true;
        }
    
      } catch (error) {
        console.error("Payment error:", error);
        this.selectionError = "Something went wrong. Please try again.";
        this.showError = true;
      }
    
      return true;
    },
    async fetchEventDetails() {
      const { eventID } = this.getQueryParams();
      try {
        const res = await fetch(`http://localhost:5001/event/${eventID}`);
        const data = await res.json();
        if (data.code === 200) {
          this.eventName = data.data.eventName;  // ✅ store the name
        } else {
          console.error("Failed to fetch event:", data.message);
        }
      } catch (e) {
        console.error("Error fetching event:", e);
      }
    }
    
    
  
  },
  computed: {
    selectedCount() {
      return this.selectedSeats.length;
    },
    canCheckout() {
      return this.selectedSeats.length >= 1 && this.selectedSeats.length <= this.maxSelectionLimit;
    }
  },
  mounted() {
    this.fetchSeats();
    this.fetchEventDetails();
  }
});

app.mount('#app');
