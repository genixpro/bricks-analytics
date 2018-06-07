import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Button, Grid, Row, Col, Dropdown, MenuItem, Well, Table, Checkbox} from 'react-bootstrap';
import _ from 'underscore';
import NumberFormat from 'react-number-format';
import MiniPosReceiptArea from './mini_pos_receipt_area';
import axios from "axios/index";

class MiniPos extends React.Component {
    constructor() {
        super();
        this.state = {
            items: [],
            subtotal: 0,
            taxes: 0,
            total: 0,
            lostSales: {}
        };

        this.secondaryWindow = window.open("/minipos_secondary", "secondaryWindow", "width=1024,height=768");
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

    finishTransaction()
    {
        axios({
            method: 'post',
            url: '/transactions',
            data: {
                timestamp: new Date().toISOString(),
                items: this.state.items,
                subtotal: this.state.subtotal,
                taxes: this.state.taxes,
                total: this.state.total,
                lostSales: {}
            }
        }).then((result) =>
        {
            this.setState({
                items: [],
                subtotal: 0,
                taxes: 0,
                total: 0,
                lostSales: {}
            });
            alert('Success!');
        }, (error) => alert("Could not make transaction. " + error.toString()));
    }


    setState(newState, callback)
    {
        super.setState(newState, callback);
        this.secondaryWindow.postMessage(newState, "*");
    }


    render() {
        return (
            <Grid fluid={true} className={"mini_pos"}>
                <div className={"left-half"} onClick={this.onReceiptAreaClicked.bind(this)}>
                    <MiniPosReceiptArea
                        items={this.state.items}
                        subtotal={this.state.subtotal}
                        taxes={this.state.taxes}
                        total={this.state.total}
                    />
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

                    <div className={"receipt-control-wrapper"}>
                        <div className={"receipt-controls"}>
                            <Well bsSize="small" className={"receipt-control-buttons"}>
                                <Button bsStyle={'primary'} onClick={this.finishTransaction.bind(this)}>Finish & Pay</Button>
                            </Well>
                            <div className={"receipt-lost-sales-wrapper"}>
                                {
                                    this.state.showLostSales ?
                                        <Well onClick={this.resetHideLostSaleWidgetTimeout.bind(this)} bsSize="small" >
                                            <p>
                                                <span>LS:&nbsp;&nbsp;</span>
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
                        <Button className={"show-lost-sales-button"} bsStyle={'default pull-right'} onClick={this.toggleLostSaleOptions.bind(this)}>
                            {
                                this.state.showLostSales
                                    ? <i className={"fa fa-eye-slash"}/>
                                    : <i className={"fa fa-eye"}/>
                            }
                        </Button>
                    </div>
                </div>
            </Grid>
        );
    }
}

export default MiniPos;
