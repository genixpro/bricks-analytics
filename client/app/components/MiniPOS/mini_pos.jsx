import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Button, Grid, Row, Col, Dropdown, MenuItem, Well, Table, Checkbox} from 'react-bootstrap';
import _ from 'underscore';
import NumberFormat from 'react-number-format';

class MiniPos extends React.Component {
    constructor() {
        super();
        this.state = {
            items: [],
            subtotal: 0,
            taxes: 0,
            total: 0,
            lostSales: {}
        }
    }


    onReceiptAreaClicked()
    {
        const elem = document.getElementById('receipt-barcode-input');
        elem.focus();
    }


    barcodeChanged(event)
    {
        const barcodeNumber = event.target.value;
        this.setState({barcode: barcodeNumber});
    }




    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.state.hideLSWidgetTimeout)
        {
            clearTimeout(this.state.hideLSWidgetTimeout);
        }
    }

    resetHideLostSaleWidgetTimeout()
    {
        if (this.state.hideLSWidgetTimeout)
        {
            clearTimeout(this.state.hideLSWidgetTimeout);
        }

        const hideLSWidgetTimeout = setTimeout(() =>
        {
            this.setState({showLostSales: false, hideLSWidgetTimeout: null});
        }, 3000);
        this.setState({hideLSWidgetTimeout});
    }



    onBarcodeSubmit(event)
    {
        event.preventDefault();

        const barcodeNumber = this.state.barcode;

        if (barcodeNumber) {

            // First check to see if there are any items already matching this barcode
            const existingItem = _.findWhere(this.state.items, {"barcode": barcodeNumber});

            if (existingItem) {
                existingItem.quantity += 1;

                const newItems = this.state.items.concat([]);
                this.updateTotals(newItems);
                this.setState({items: newItems, barcode: ""});
            }
            else {
                let newItem = null;
                if (barcodeNumber === "1") {
                    newItem = {
                        "name": "onion",
                        "price": 3.99,
                        "quantity": 1,
                        "barcode": barcodeNumber
                    }
                }

                if (newItem) {
                    const newItems = this.state.items.concat([newItem]);
                    this.updateTotals(newItems);
                    this.setState({items: newItems, barcode: ""});
                }
                else {
                    this.setState({barcode: ""});
                    alert("We have no item with this barcode.");
                }
            }
        }
    }


    updateTotals(items)
    {
        let subtotal = 0;
        items.forEach((item) => {
            subtotal += item.price * item.quantity;
        });

        const taxes = subtotal * 0.13;

        const total = subtotal + taxes;

        this.setState({
            subtotal: subtotal,
            taxes: taxes,
            total: total
        })
    }

    toggleLostSaleOptions()
    {
        const showLostSales = this.state.showLostSales;
        this.setState({showLostSales: !showLostSales});
        this.resetHideLostSaleWidgetTimeout();
    }

    toggleLostSale(sku)
    {
        const newLostSales = _.clone(this.state.lostSales);
        newLostSales[sku] = !newLostSales[sku];
        this.setState({lostSales: newLostSales});
    }


    render() {
        return (
            <Grid fluid={true} className={"mini_pos"}>
                <div className={"left-half"} onClick={this.onReceiptAreaClicked.bind(this)}>
                    <Well bsSize="large" className={"receipt-well"}>
                        <Row className={"receipt-header"}>
                            <Col xs={12}>
                                <div className={"date"}>{new Date().toString()}</div>
                            </Col>
                        </Row>
                        <Row className={"receipt-body"}>
                            <Col xs={12}>
                                <Table striped bordered condensed hover>
                                    <thead>
                                        <tr>
                                            <th className={"name-column"}>Name</th>
                                            <th className={"quantity-column"}>Quantity</th>
                                            <th className={"each-column"}>Each</th>
                                            <th className={"total-column"}>Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {
                                            this.state.items.map((item, index) =>
                                            {
                                              return <tr key={index}>
                                                    <td className={"name-column"}>{item.name}</td>
                                                    <td className={"quantity-column"}>{item.quantity}</td>
                                                    <td className={"each-column"}><NumberFormat value={item.price} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></td>
                                                    <td className={"total-column"}><NumberFormat value={item.price * item.quantity} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></td>
                                                </tr>;
                                            })
                                        }
                                    </tbody>
                                </Table>
                            </Col>
                        </Row>
                        <Row className={"receipt-total-row"}>
                            <Col xs={4} xsOffset={8}>
                                <h3>Subtotal&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.subtotal} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                                <h3>Taxes&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.taxes} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                                <h2>Total&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.total} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h2>
                            </Col>
                        </Row>
                    </Well>
                    <div className={"receipt-barcode-input-wrapper"}>
                        <form onSubmit={this.onBarcodeSubmit.bind(this)} action="#">
                            <input type={"text"} id={'receipt-barcode-input'} value={this.state.barcode} onChange={this.barcodeChanged.bind(this)} />
                        </form>
                    </div>
                </div>
                <div className={"right-half"}>
                    <Well bsSize="large" className={"ad-well"} onClick={this.onReceiptAreaClicked.bind(this)}>
                        <h1>Mini POS</h1>
                        <img src={"/img/loblaws_logo.svg"} />
                    </Well>


                    <div className={"receipt-lost-sales-wrapper"}>
                        <Button bsStyle={'default pull-right'} onClick={this.toggleLostSaleOptions.bind(this)}>
                            {
                                this.state.showLostSales
                                ? <i className={"fa fa-eye-slash"}/>
                                : <i className={"fa fa-eye"}/>
                            }
                        </Button>
                        {
                            this.state.showLostSales ?
                                <Well onClick={this.resetHideLostSaleWidgetTimeout.bind(this)}>
                                    <p>
                                        <span>Select L/S:&nbsp;&nbsp;</span>
                                        <Checkbox checked={this.state.lostSales['chips']} onChange={this.toggleLostSale.bind(this, "chips")}>
                                            Chips
                                        </Checkbox>
                                        <Checkbox checked={this.state.lostSales['guacamole']} onChange={this.toggleLostSale.bind(this, "guacamole")}>
                                            Guacamole
                                        </Checkbox>
                                        <Checkbox checked={this.state.lostSales['deodorant']} onChange={this.toggleLostSale.bind(this, "deodorant")}>
                                            Deodorant
                                        </Checkbox>
                                        <Checkbox checked={this.state.lostSales['shaving']} onChange={this.toggleLostSale.bind(this, "shaving")}>
                                            Shaving Cream
                                        </Checkbox>
                                    </p>
                                </Well>
                                : null
                        }
                    </div>
                </div>
            </Grid>
        );
    }
}

export default MiniPos;
